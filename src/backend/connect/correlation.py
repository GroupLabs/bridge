import numpy as np
from numpy.linalg import norm

CORR_EMBEDDING_DIM = 256

def correlation_embedding(column: np.array, dim: int=CORR_EMBEDDING_DIM):
    fft_magnitude = np.abs(np.fft.fft(column))

    if np.linalg.norm(fft_magnitude) == 0: # dont divide by zero
        normalized_magnitude = fft_magnitude
    else:
        normalized_magnitude = fft_magnitude / norm(fft_magnitude)

    return normalized_magnitude.tolist()[:dim]


if __name__ == "__main__":
    import pandas as pd

    target_df = pd.read_parquet("../../../data/datasets/higgs/target.parquet")
    m_df = pd.read_parquet("../../../data/datasets/higgs/m.parquet")
    lepton_df = pd.read_parquet("../../data/datasets/higgs/lepton.parquet")
    jet_df = pd.read_parquet("../../../data/datasets/higgs/jet.parquet")

    mat_a = correlation_embedding(target_df["target"].to_numpy())
    mat_b = correlation_embedding(m_df["m_bb"].to_numpy()) # highest pearson correlation
    mat_c= correlation_embedding(lepton_df["lepton_pT"].to_numpy()) # medium pearson correlation
    mat_d= correlation_embedding(jet_df["jet_4_eta"].to_numpy()) # lowest pearson correlation


    cosine_similarity = np.dot(mat_a, mat_b)

    cosine_distance = 1 - cosine_similarity

    print("Cosine similarity:", cosine_similarity)

    cosine_similarity = np.dot(mat_a, mat_c)

    cosine_distance = 1 - cosine_similarity

    print("Cosine similarity:", cosine_similarity)

    cosine_similarity = np.dot(mat_a, mat_d)

    cosine_distance = 1 - cosine_similarity

    print("Cosine similarity:", cosine_similarity)
