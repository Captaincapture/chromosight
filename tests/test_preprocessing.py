import numpy as np
import unittest
from nose2.tools import params
import scipy.sparse as sp
import chromosight
import chromosight.utils
import chromosight.utils.preprocessing as preproc
import chromosight.utils.io as cio

mat, chroms, bins, res = cio.load_cool("data_test/example.cool")
mat = mat.tocsr()
# Get all intra-chromosomal matrices
intra_mats = [
    mat[s:e, s:e] for s, e in zip(chroms["start_bin"], chroms["end_bin"])
]


class TestPreprocessing(unittest.TestCase):
    def test_get_detectable_bins(self):
        """Check if correct bin indices are reported as detectable."""
        # Make random matrix using uniform sample between 0 and 1
        uniform_mat = sp.random(1000, 1000, density=0.1, format="csr")
        # introduce outlier bin
        uniform_mat[10, :] = 0.0
        uniform_mat[:, 10] = 0.0
        uniform_mat = uniform_mat.tocoo()
        uniform_mat.eliminate_zeros()
        det_bins = preproc.get_detectable_bins(
            uniform_mat, inter=False, n_mads=1
        )
        # Check if symmetric mode return same detectable rows and cols
        assert np.all(det_bins[0] == det_bins[1])
        # Check if the right bin index is indetectable
        assert 10 not in det_bins[0]
        asym_mat = sp.random(100, 1000, 0.1, format="csr")
        asym_mat[10, :] = 0
        asym_mat[:, 6] = 0
        asym_mat = asym_mat.tocoo()
        asym_mat.eliminate_zeros()
        asym_mat.data *= 1000
        det_bins = preproc.get_detectable_bins(asym_mat, inter=True, n_mads=1)
        # Ensure correct index was removed in both dimensions
        assert 10 not in det_bins[0]
        assert 6 not in det_bins[1]
        # Ensure asymmetric interchromosomal matrix as input results in crash
        with self.assertRaises(ValueError):
            preproc.get_detectable_bins(asym_mat, inter=False)

    @params(100000000, 10e10)
    def test_subsample_contacts_exceed(self, n_contacts):
        """Oversampling should result in value errors"""
        with self.assertRaises(ValueError):
            preproc.subsample_contacts(mat, n_contacts)


@params(*intra_mats)
def test_normalize(matrix):
    """Check if normalization sets all bins sums to ~1 (0.5 for upper triangle)."""
    norm = preproc.normalize(matrix, good_bins=None, iterations=50)
    sym_norm = norm + norm.T
    sym_norm.setdiag(sym_norm.diagonal(0) / 2)
    bin_sums = sym_norm.sum(axis=1).A1
    # Replace missing bins by ones for the sake of testing
    bin_sums[bin_sums == 0] = 1
    assert np.all(np.isclose(bin_sums, np.ones(matrix.shape[0]), rtol=0.1))


@params(*intra_mats)
def test_diag_trim(matrix):
    """Check if trimming diagonals preserves shape and sets diagonals to zero."""
    for d in range(matrix.shape[0]):
        trimmed = preproc.diag_trim(matrix.todia(), d)
        diag_sums = [
            trimmed.diagonal(d).sum() for d in range(trimmed.shape[0])
        ]
        assert trimmed.shape == matrix.shape
        assert np.sum(diag_sums[d + 1 :]) == 0


def test_despeckle():
    """Check that artificially added outliers are removed"""
    # Make random matrix using uniform sample between 0 and 1
    uniform_mat = sp.random(1000, 1000, 0.1, format="csr")
    # introduce outlier on 11th diag
    uniform_mat[10, 10] = 10e6
    # Compute median of 11th diag (desired value after despeckling)
    exp_val = np.median(uniform_mat.diagonal(10))
    desp = preproc.despeckle(uniform_mat.tocoo(), th2=1)
    assert np.max(uniform_mat.data) > np.max(desp.data)
    assert desp.tocsr()[10, 10] == exp_val


def test_resize_kernel():
    """
    Ensure resized kernels are of appropriate size and centered and contain
    expected values.
    """
    m = 15
    # Restrict minimum and maximum dimensions of resized kernels
    min_allowed_dim, max_allowed_dim = 5, 101
    # Use a simple point to check if result is centered
    point_kernel = np.zeros((m, m))
    point_kernel[m // 2, m // 2] = 10
    # Try with different combinations of source and target resolutions
    res_list = [3, 900, 5000, 10000]
    for kernel_res in res_list:
        for signal_res in res_list:
            exp_dim = int(m * kernel_res / signal_res)
            if not exp_dim % 2:
                exp_dim -= 1
            obs_kernel = preproc.resize_kernel(
                point_kernel,
                kernel_res=kernel_res,
                signal_res=signal_res,
                min_size=min_allowed_dim,
                max_size=max_allowed_dim,
            )
            obs_kernel_factor = preproc.resize_kernel(
                point_kernel,
                factor=kernel_res / signal_res,
                min_size=min_allowed_dim,
                max_size=max_allowed_dim,
            )

            obs_dim = obs_kernel.shape[0]
            obs_dim_factor = obs_kernel_factor.shape[0]
            assert obs_dim == obs_kernel.shape[1]
            assert obs_dim == obs_dim_factor
            assert obs_dim == max(
                min(max_allowed_dim, exp_dim), min_allowed_dim
            )
            assert np.max(obs_kernel) == obs_kernel[obs_dim // 2, obs_dim // 2]


def test_distance_law():
    """Test if the distance law array has the right dimensions and expected values"""
    m = np.ones((3, 3))
    m += np.array([1, 2, 3])
    # Test regular distance law
    dist_law = preproc.distance_law(sp.csr_matrix(m), smooth=False)
    assert np.all(dist_law == np.array([3.0, 3.5, 4.0]))
    assert dist_law.shape == (3,)
    # Test distance law with isotonic regression: values should not go up
    dist_law = preproc.distance_law(sp.csr_matrix(m), smooth=True)
    assert np.all(dist_law == np.array([3.5, 3.5, 3.5]))
    assert dist_law.shape == (3,)


@params(*intra_mats)
def test_detrend(matrix):
    """Basic test: Check if detrended matrix pixels have lower standard deviation"""
    detrended = preproc.detrend(matrix)
    for d in range(matrix.shape[0] // 10):
        assert matrix.diagonal(d).std() > detrended.diagonal(d).std()


@params(*intra_mats)
def test_ztransform(matrix):
    """Check if z-transformation yields mean 0 and std 1"""
    ztr = preproc.ztransform(matrix)
    assert np.isclose(np.mean(ztr.data), 0, rtol=0.1)
    assert np.isclose(np.std(ztr.data), 1, rtol=0.1)


def test_signal_to_noise_threshold():
    """Check if SNR yields correct index on synthetic matrix."""
    # Initialize empty matrix (SNR = 0)
    syn_mat = sp.coo_matrix((1000, 1000))
    # Set all values in 5th first diagonals to 10 (SNR = 10)
    for k in range(5):
        syn_mat.setdiag(10, k=k)
    snr_idx = preproc.signal_to_noise_threshold(syn_mat, detectable_bins=None)
    # Since the 5th first diagonals are good, the last scannable diagonal
    # should be 4
    assert snr_idx == 5


@params(*intra_mats)
def test_sum_mat_bins(mat):
    """Check if bin sum on upper triangle matrix yields expected results."""
    sym_mat = mat + mat.T
    sym_mat.setdiag(sym_mat.diagonal() / 2)
    summed = preproc.sum_mat_bins(sym_mat)
    exp_sum = 2 * sym_mat.sum(axis=1).A1 - sym_mat.diagonal()
    assert np.all(np.isclose(exp_sum, summed, rtol=0.1))


@params(0, 0.1, 0.5, 0.8, 1)
def test_subsample_contacts_prop(prop):
    """Test sampling proportions of contacts"""
    sampled = preproc.subsample_contacts(
        mat.tocoo(), int(prop * mat.data.sum())
    )
    assert np.isclose(sampled.data.sum(), mat.data.sum() * prop, rtol=0.1)


@params(2, 100, 10000)
def test_subsample_contacts_count(n_contacts):
    """Test sampling raw contact counts"""
    sampled = preproc.subsample_contacts(mat.tocoo(), n_contacts)
    assert np.isclose(sampled.data.sum(), n_contacts, rtol=0.1)
