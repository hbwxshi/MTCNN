import numpy as np
import sklearn
from sklearn.linear_model import LinearRegression
from sklearn.metrics import roc_curve
from scipy.special import expit
from similarity.cosine import Cosine
from similarity.base import Similarity


class QMagFace(Similarity):
    def __init__(self, alpha=0, beta=0):
        self.beta = beta
        self.alpha = alpha

    def similarity(self, f1, f2):
        s, q = self._compute_s_q(f1, f2)
        omega = self.beta * s - self.alpha
        omega[omega >= 0] = 0
        return omega * q + s

    def train(self, f1, f2, y, weights_num=20, fmr_num=50, fmr_min=1e-5, fmr_max=1e-2, max_ratio=0.5):
        # fmr_num logarithmically spaced values from the given range of FMRs
        fmrs = np.logspace(np.log10(fmr_min), np.log10(fmr_max), num=fmr_num)
        s, q = self._compute_s_q(f1, f2)
        max_q = np.max(q)
        max_omega = max_ratio / max_q
        # The list of quality weights we consider as possible solutions
        omegas = np.linspace(-max_omega, max_omega, num=weights_num)
        ts = np.zeros((fmr_num,))
        omega_opts = np.zeros((fmr_num,))
        # Create temporary variables to store:
        # The thresholds which achieve the FMR for the respective omega
        tmp_thrs = np.zeros((weights_num, fmr_num))
        # The FNMR using omega for the given FMR
        tmp_fnmrs = np.zeros((weights_num, fmr_num))
        # For every omega compute performance at all FMR values and store it and the threshold
        for i, omega in enumerate(omegas):
            # Calculate an ROC curve with SK-Learn
            scores = expit(omega * q + s)
            fpr, tpr, thr = roc_curve(y, scores)
            # Compute and FNMR and trhreshold for every FMR
            for j, fmr in enumerate(fmrs):
                fnmr_idx = np.argmin(1 - tpr[fpr < fmr])
                fnmr = (1 - tpr[fpr < fmr])[fnmr_idx]
                threshold = thr[fnmr_idx]
                tmp_thrs[i, j] = threshold
                tmp_fnmrs[i, j] = fnmr

        # For every FMR find the best omega and the threshold that achieves this
        for j in range(fmr_num):
            fnmrs = tmp_fnmrs[:, j]
            fnmr_idx = np.argmin(fnmrs)
            ts[j] = tmp_thrs[fnmr_idx, j]
            omega_opts[j] = omegas[fnmr_idx]

        # Finally, use SK-Learn to fit a line and get m and b
        m, b = self._fit_line(np.array(ts), np.array(omega_opts))
        self.beta = m
        self.alpha = -b

    def name(self):
        return "QMagFace"

    @staticmethod
    def _fit_line(x, y):
        x_ = x.reshape(-1, 1)
        lreg = LinearRegression()
        lreg.fit(x_, y)
        m = lreg.coef_[0]
        b = lreg.intercept_
        return m, b

    @staticmethod
    def _compute_s_q(f1, f2):
        f1_normed, q1 = sklearn.preprocessing.normalize(f1, return_norm=True)
        f2_normed, q2 = sklearn.preprocessing.normalize(f2, return_norm=True)
        s = Cosine.similarity(f1_normed, f2_normed, is_normed=True)
        q = np.min(np.stack([q1, q2]), 0)
        return s, q
