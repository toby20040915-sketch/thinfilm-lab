import numpy as np
import pytest
from scipy.integrate import quad
from tmm import inc_tmm, coh_tmm
from thinfilm.physics import Parameters, corrected_weight, ATLU, spectrum, HC


def test_corrected_urbach_zero_and_C1_join():
    p = Parameters()
    assert corrected_weight([0], p)[0] == 0
    e, h = p.Ec_eV, 1e-6
    f = corrected_weight(np.array([e-h, e, e+h]), p)
    assert (f[2]-f[1])/h == pytest.approx((f[1]-f[0])/h, rel=1e-4)


@pytest.mark.parametrize("energy", [.2, 1.6, 3.5, 8.])
def test_ATLU_against_independent_adaptive_integral(energy):
    p = Parameters()
    z = energy+.02j
    def integrand(x):
        f = float(corrected_weight(np.array([x]), p)[0])
        return f*(1/(x-z)+1/(x+z))/np.pi
    intervals = sorted(set([0, p.Ec_eV, max(0, energy-.2), energy, energy+.2, 20, 160]))
    direct = 1+0j
    for a, b in zip(intervals[:-1], intervals[1:]):
        direct += quad(lambda x: integrand(x).real, a, b, epsabs=1e-9, limit=250)[0]
        direct += 1j*quad(lambda x: integrand(x).imag, a, b, epsabs=1e-9, limit=250)[0]
    calculated = ATLU([energy], step_eV=.005).dielectric(p)[0]
    assert calculated == pytest.approx(direct, rel=2e-5, abs=8e-5)


def test_bare_substrate_and_energy_conservation():
    w = np.linspace(300, 1200, 40)
    sp = spectrum(w, np.full(40, 2.5), np.zeros(40), 0, 1.5)
    assert np.allclose(sp["T"], 2*1.5/(1+1.5**2))
    assert np.allclose(sp["R"]+sp["T"], 1.)
    sp = spectrum(w, np.full(40, 2.5), np.zeros(40), 300, 1.5)
    assert np.allclose(sp["R"]+sp["T"], 1., atol=1e-12)


@pytest.mark.parametrize("backside", [True, False])
@pytest.mark.parametrize("k", [0., .2, 3.])
def test_optics_against_independent_tmm(backside, k):
    w = np.array([350., 550., 900.])
    sp = spectrum(w, np.full(3, 3.1), np.full(3, k), 78, 1.52, backside)
    for j, wl in enumerate(w):
        if backside:
            expected = inc_tmm("s", [1, 3.1+1j*k, 1.52, 1], [np.inf, 78, 1e6, np.inf],
                               ["i", "c", "i", "i"], 0, wl)
        else:
            expected = coh_tmm("s", [1, 3.1+1j*k, 1.52], [np.inf, 78, np.inf], 0, wl)
        for key in ("T", "R"):
            assert sp[key][j] == pytest.approx(expected[key], abs=2e-12)


def test_opaque_stability_and_scattering_power_accounting():
    sp = spectrum([500.], [3.], [10.], 1e5, scatter_q=.1)
    assert np.isfinite(sp["R"]).all() and sp["T"][0] < 1e-20
    assert np.allclose(sp["R"]+sp["T"]+sp["A_intrinsic"]+sp["scattered_loss"], 1.)


def test_passivity_and_grid_convergence():
    p = Parameters()
    e = np.linspace(.5, 6, 81)
    a = ATLU(e).dielectric(p)
    b = ATLU(e, step_eV=.005, cutoff_eV=320).dielectric(p)
    assert np.all(a.imag > 0)
    assert np.max(np.abs(a-b)) < .001


def test_opaque_spectra_do_not_identify_thickness():
    w = np.linspace(350., 750., 40)
    a = spectrum(w, np.full(40, 3.), np.full(40, 3.), 1000.)
    b = spectrum(w, np.full(40, 3.), np.full(40, 3.), 2000.)
    assert max(np.max(np.abs(a[c]-b[c])) for c in ("T", "R")) < 1e-12
