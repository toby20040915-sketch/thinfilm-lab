"""ATLU dispersion and stable normal-incidence optical scattering.

ATLU: Ballester et al., Coatings 12 (2022) 1549, Eqs. 6-9.
We numerically integrate Eq. 6, rather than use branch-sensitive Ei formulas.
The time convention is exp(-i omega t), so passive N = n + i k.
"""
from dataclasses import dataclass, asdict
import numpy as np

HC = 1239.8419843320026  # eV nm


@dataclass
class Parameters:
    d_nm: float = 80.0
    A_eV: float = 100.0
    Eg_eV: float = 1.6
    gap_eV: float = 1.8  # E0 - Ec; parameterization guarantees E0 > Ec > Eg
    C_eV: float = 2.0
    tail_fraction: float = 0.08  # Ec = Eg * (1 + tail_fraction)
    scatter_q: float = 0.0  # optical depth at 550 nm; NOT AFM RMS roughness

    @property
    def Ec_eV(self):
        return self.Eg_eV * (1 + self.tail_fraction)

    @property
    def E0_eV(self):
        return self.Ec_eV + self.gap_eV

    @property
    def Eu_eV(self):
        e, eg, e0, c = self.Ec_eV, self.Eg_eV, self.E0_eV, self.C_eV
        D = (e*e-e0*e0)**2 + c*c*e*e
        # Matching d(log(epsilon2))/dE on both sides of Ec (Eq. 9).
        inv = 2/(e-eg) - 2/e - (4*e*(e*e-e0*e0)+2*c*c*e)/D
        if inv <= 0 or not np.isfinite(inv):
            raise ValueError("TLU 接點不符合正 Urbach 能量，請調整參數範圍。")
        return 1/inv

    def validate(self):
        if not all(np.isfinite(v) for v in asdict(self).values()):
            raise ValueError("參數必須為有限數值。")
        if min(self.A_eV, self.Eg_eV, self.gap_eV, self.C_eV, self.tail_fraction) <= 0:
            raise ValueError("色散參數必須大於零。")
        if self.d_nm < 0 or self.scatter_q < 0:
            raise ValueError("厚度與散射係數不得為負。")
        _ = self.Eu_eV

    def report(self):
        return dict(asdict(self), Ec_eV=self.Ec_eV, E0_eV=self.E0_eV, Eu_eV=self.Eu_eV)


def corrected_weight(energy, p):
    """Positive-energy part of corrected TLU epsilon2; odd extension in ATLU."""
    e = np.asarray(energy, float)
    if np.any(e < 0):
        raise ValueError("積分能量不得為負。")
    ec, e0, eg, c = p.Ec_eV, p.E0_eV, p.Eg_eV, p.C_eV
    dc = (ec*ec-e0*e0)**2 + c*c*ec*ec
    fc = p.A_eV*e0*c*(ec-eg)**2/(ec*dc)
    # This form avoids separately evaluating a very small Au and a large exp(E/Eu).
    tail = fc*(e/ec)*np.exp(np.minimum((e-ec)/p.Eu_eV, 0))
    safe_e = np.maximum(e, 1e-100)
    tl = p.A_eV*e0*c*(e-eg)**2/(safe_e*((e*e-e0*e0)**2+c*c*e*e))
    return np.where(e <= ec, tail, tl)


class ATLU:
    """Causal transform of a piecewise-linear weight on [0, cutoff].

    Integral for an odd weight f:
      epsilon(z) = 1 + 1/pi * integral_0^inf f(x)[1/(x-z)+1/(x+z)] dx.
    Integrate each linear segment exactly using complex logarithms. This avoids
    sampling a narrow Lorentzian kernel and makes small fixed Gamma practical.
    Grid/cutoff convergence is checked independently after each fit.
    """
    def __init__(self, energy, gamma_eV=0.02, step_eV=0.01, cutoff_eV=160.0):
        self.energy = np.atleast_1d(np.asarray(energy, float))
        if (np.any(~np.isfinite(self.energy)) or np.any(self.energy <= 0)
                or not np.isfinite(gamma_eV) or gamma_eV <= 0
                or not np.isfinite(step_eV) or step_eV <= 0
                or not np.isfinite(cutoff_eV) or cutoff_eV <= max(30, self.energy.max()*2)):
            raise ValueError("ATLU 能量、展寬或積分範圍無效。")
        self.gamma_eV, self.step_eV, self.cutoff_eV = gamma_eV, step_eV, cutoff_eV
        dense_end = max(20., self.energy.max()+5)
        self.grid = np.unique(np.r_[np.arange(0, dense_end, step_eV),
                                    np.geomspace(dense_end, cutoff_eV, 180)])
        a, b = self.grid[:-1], self.grid[1:]
        h = b-a
        z = (self.energy + 1j*gamma_eV)[:, None]
        kernel = np.zeros((len(self.energy), len(self.grid)), complex)
        for pole in (z, -z):
            log = np.log(b-pole)-np.log(a-pole)
            left = ((b-pole)*log-h)/h
            right = (h+(pole-a)*log)/h
            kernel[:, :-1] += left/np.pi
            kernel[:, 1:] += right/np.pi
        self.kernel = kernel

    def dielectric(self, p):
        p.validate()
        return 1 + self.kernel @ corrected_weight(self.grid, p)

    def nk(self, p):
        eps = self.dielectric(p)
        N = np.sqrt(eps.astype(complex))
        return N.real, N.imag


def coherent_rt(wavelength, N, d_nm, n_in, n_out):
    """Air/one absorbing film/transparent substrate, including reverse incidence.

    Scattering amplitudes use exp(+i delta), so thick absorbing films underflow
    harmlessly instead of overflowing characteristic matrices.
    """
    wl = np.asarray(wavelength, float)
    a, b, c = np.asarray(n_in), np.asarray(N), np.asarray(n_out)
    r01, r12 = (a-b)/(a+b), (b-c)/(b+c)
    t01, t12 = 2*a/(a+b), 2*b/(b+c)
    phase = np.exp(2j*np.pi*b*d_nm/wl)
    denom = 1+r01*r12*phase**2
    r = (r01+r12*phase**2)/denom
    t = t01*t12*phase/denom
    return np.abs(r)**2, np.real(c)/np.real(a)*np.abs(t)**2


def spectrum(wavelength, n, k, d_nm, substrate_n=1.5, backside=True,
             scatter_q=0., scatter_power=4.):
    """Transparent, thick incoherent substrate in air; normal incidence only.

    Optional exp[-q(550/lambda)^power] is an empirical loss of collected specular
    R and T. Missing scattered power is reported separately from absorption.
    """
    wl = np.asarray(wavelength, float)
    s = np.broadcast_to(np.asarray(substrate_n, float), wl.shape)
    n, k = np.broadcast_arrays(np.asarray(n, float), np.asarray(k, float))
    if (np.any(~np.isfinite(wl)) or np.any(wl <= 0) or np.any(~np.isfinite(s))
            or np.any(s < 1) or np.any(~np.isfinite(n+k)) or np.any(n <= 0)
            or np.any(k < 0) or not np.isfinite(d_nm+scatter_q+scatter_power)
            or d_nm < 0 or scatter_q < 0 or scatter_power <= 0):
        raise ValueError("光學模型輸入無效；此版本只接受透明基板 n >= 1。")
    N = n+1j*k
    rf, tf = coherent_rt(wl, N, d_nm, 1., s)
    if backside:
        rb, tb = coherent_rt(wl, N, d_nm, s, 1.)
        rs = ((s-1)/(s+1))**2
        denominator = 1-rb*rs
        T = tf*(1-rs)/denominator
        R = rf+tf*rs*tb/denominator
    else:
        R, T = rf, tf
    survival = np.exp(-scatter_q*(550/wl)**scatter_power)
    return {"T": T*survival, "R": R*survival, "T_intrinsic": T,
            "R_intrinsic": R, "A_intrinsic": 1-T-R,
            "scattered_loss": (1-survival)*(T+R)}
