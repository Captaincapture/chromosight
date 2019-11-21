from nose2.tools import params
import tempfile
import os
import numpy as np
import chromosight.utils.plotting as cup
import chromosight.utils.detection as cud
import chromosight.utils.io as cio


mat, chroms, bins, res = cio.load_cool("data_test/example.cool")

mat = mat.tocsr()
#  Get all intra-chromosomal matrices
intra_mats = [
    mat[s:e, s:e] for s, e in zip(chroms["start_bin"], chroms["end_bin"])
]

pattern_list = []
window_list = []


class TestPlotting:
    def __init__(self):
        """Setup function to generate a named tempfile"""
        # Create tmp temporary file for reading and writing
        tmp_out = tempfile.NamedTemporaryFile(delete=False)
        tmp_out.close()
        # Give access to full path, dirname and basename in diff variables
        self.tmp_path = tmp_out.name
        self.tmp_dir = os.path.dirname(self.tmp_path)
        self.tmp_file = os.path.basename(self.tmp_path)

    def test_distance_plot(self):
        cup.distance_plot(intra_mats, labels=None, out=self.tmp_path)

    def test_pileup_plot(self):
        windows = np.reshape(np.random.randint(100, size=1000), (10, 10, 10))
        pileup_pattern = cud.pileup_patterns(windows)
        cup.pileup_plot(
            pileup_pattern, name="pileup_patterns", output=self.tmp_dir
        )


"""
@params(*zip(pattern_list, chroms.name))
def test_plot_whole_matrix(patterns, chrom):
    region = chroms.loc[chroms.name == chrom, ["start_bin", "end_bin"]]
    cup.plot_whole_matrix(mat, patterns, out=None, region=region)
"""