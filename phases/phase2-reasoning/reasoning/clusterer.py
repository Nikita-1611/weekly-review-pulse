import numpy as np
import umap
import hdbscan
from typing import List, Dict, Tuple

def cluster_embeddings(embeddings: np.ndarray, reviews: List[Dict]) -> Tuple[Dict[int, List[Dict]], bool]:
    """
    Applies UMAP dimensionality reduction and HDBSCAN density clustering.
    Returns a tuple: (clusters_dict, all_noise_flag)
    """
    if len(embeddings) == 0:
        return {}, True
        
    if len(embeddings) < 15:
        # Not enough data for meaningful UMAP with n_neighbors=15. Fallback edge-case.
        print("Warning: Less than 15 reviews, UMAP may behave unpredictably. Defaulting all to noise cluster (-1).")
        return {-1: reviews}, True

    # UMAP Hyperparameters defined in architecture
    umap_reducer = umap.UMAP(
        n_neighbors=15, 
        n_components=5, 
        metric='cosine',
        random_state=42 # fixed seed for reproducibility
    )
    reduced_embeddings = umap_reducer.fit_transform(embeddings)

    # HDBSCAN Hyperparameters defined in architecture
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=10,
        min_samples=5,
        cluster_selection_epsilon=0.1
    )
    cluster_labels = clusterer.fit_predict(reduced_embeddings)

    clusters = {}
    all_noise = True
    
    for i, label in enumerate(cluster_labels):
        if label != -1:
            all_noise = False
            
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(reviews[i])

    # Edge Case: All reviews fall into HDBSCAN noise (no clusters formed)
    if all_noise:
        return clusters, True

    # Cap to top 5 largest non-noise clusters (saves LLM tokens, focuses report)
    MAX_CLUSTERS = 5
    non_noise = {k: v for k, v in clusters.items() if k != -1}
    if len(non_noise) > MAX_CLUSTERS:
        sorted_clusters = sorted(non_noise.items(), key=lambda x: len(x[1]), reverse=True)
        top_clusters = dict(sorted_clusters[:MAX_CLUSTERS])
        # Merge remaining small clusters into noise
        noise_reviews = clusters.get(-1, [])
        for _, reviews_list in sorted_clusters[MAX_CLUSTERS:]:
            noise_reviews.extend(reviews_list)
        clusters = top_clusters
        if noise_reviews:
            clusters[-1] = noise_reviews
        
    return clusters, False
