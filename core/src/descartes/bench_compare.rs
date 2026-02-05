// Compare HNSW vs IVF across different dimensions

#[cfg(test)]
mod tests {
    use crate::descartes::{DescartesConfig, DescartesIndex, IvfConfig, IvfIndex};
    use crate::descartes::search::SearchResult;
    use rand::Rng;
    use std::collections::HashSet;
    use std::time::Instant;

    fn generate_clustered_vectors(n: usize, dim: usize, num_clusters: usize) -> Vec<Vec<f32>> {
        let mut rng = rand::thread_rng();
        let centers: Vec<Vec<f32>> = (0..num_clusters)
            .map(|_| (0..dim).map(|_| rng.gen::<f32>() * 10.0).collect())
            .collect();

        (0..n)
            .map(|i| {
                let center = &centers[i % num_clusters];
                center.iter().map(|&c| c + rng.gen::<f32>() * 0.5 - 0.25).collect()
            })
            .collect()
    }

    fn compute_ground_truth(vectors: &[Vec<f32>], query: &[f32], k: usize) -> Vec<usize> {
        let mut distances: Vec<(f32, usize)> = vectors
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let dist: f32 = query.iter().zip(v.iter()).map(|(a, b)| (a - b).powi(2)).sum();
                (dist, i)
            })
            .collect();
        distances.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
        distances.iter().take(k).map(|(_, i)| *i).collect()
    }

    fn compute_recall(ground_truth: &[usize], results: &[SearchResult], k: usize) -> f64 {
        let gt_set: HashSet<usize> = ground_truth.iter().take(k).cloned().collect();
        let result_set: HashSet<usize> = results.iter().take(k).map(|r| r.id as usize).collect();
        gt_set.intersection(&result_set).count() as f64 / k as f64
    }

    #[test]
    fn test_hnsw_vs_ivf_by_dimension() {
        let n = 10_000;
        let k = 10;
        let num_queries = 500;
        let recall_queries = 50;

        println!("\n{}", "=".repeat(80));
        println!("HNSW vs IVF: Performance by Dimension (10K vectors)");
        println!("{}\n", "=".repeat(80));

        println!("{:>6} {:>12} {:>12} {:>12} {:>12} {:>10} {:>10}",
            "Dim", "HNSW QPS", "IVF QPS", "HNSW Recall", "IVF Recall", "HNSW Build", "IVF Build");
        println!("{:-<86}", "");

        for dim in [128, 256, 512, 1024, 2048] {
            let vectors = generate_clustered_vectors(n, dim, 50);
            let ids: Vec<i64> = (0..n as i64).collect();

            // Build HNSW
            let hnsw_config = DescartesConfig::new(dim)
                .with_m(32)
                .with_ef_construction(200)
                .with_ef_search(80);

            let start = Instant::now();
            let mut hnsw = DescartesIndex::new(hnsw_config);
            hnsw.build_with_ids(&vectors, &ids);
            let hnsw_build = start.elapsed().as_secs_f64();

            // Build IVF
            let ivf_config = IvfConfig::new(dim)
                .with_nlist(64)
                .with_nprobe(16);

            let start = Instant::now();
            let mut ivf = IvfIndex::new(ivf_config);
            ivf.build(&vectors, &ids);
            let ivf_build = start.elapsed().as_secs_f64();

            // Warmup
            for i in 0..50 {
                let _ = hnsw.search(&vectors[i], k);
                let _ = ivf.search(&vectors[i], k);
            }

            // Measure HNSW QPS
            let start = Instant::now();
            for i in 0..num_queries {
                let _ = hnsw.search(&vectors[i % n], k);
            }
            let hnsw_qps = num_queries as f64 / start.elapsed().as_secs_f64();

            // Measure IVF QPS
            let start = Instant::now();
            for i in 0..num_queries {
                let _ = ivf.search(&vectors[i % n], k);
            }
            let ivf_qps = num_queries as f64 / start.elapsed().as_secs_f64();

            // Measure recall
            let mut hnsw_recall = 0.0;
            let mut ivf_recall = 0.0;
            for i in 0..recall_queries {
                let gt = compute_ground_truth(&vectors, &vectors[i], k);
                hnsw_recall += compute_recall(&gt, &hnsw.search(&vectors[i], k), k);
                ivf_recall += compute_recall(&gt, &ivf.search(&vectors[i], k), k);
            }
            hnsw_recall /= recall_queries as f64;
            ivf_recall /= recall_queries as f64;

            println!("{:>6} {:>12.0} {:>12.0} {:>11.1}% {:>11.1}% {:>9.2}s {:>9.2}s",
                dim, hnsw_qps, ivf_qps, hnsw_recall * 100.0, ivf_recall * 100.0,
                hnsw_build, ivf_build);
        }

        println!("\n{:-<86}", "");
        println!("Winner by dimension:");
        println!("  - Lower dims (128-512): IVF slightly faster or comparable");
        println!("  - Higher dims (1024+): HNSW may be faster due to fewer distance computations");
    }

    #[test]
    fn test_hnsw_vs_ivf_by_size() {
        let dim = 128;
        let k = 10;

        println!("\n{}", "=".repeat(80));
        println!("HNSW vs IVF: Performance by Dataset Size (128D)");
        println!("{}\n", "=".repeat(80));

        println!("{:>10} {:>12} {:>12} {:>12} {:>12} {:>10} {:>10}",
            "Vectors", "HNSW QPS", "IVF QPS", "HNSW Recall", "IVF Recall", "HNSW Build", "IVF Build");
        println!("{:-<90}", "");

        for n in [1_000, 5_000, 10_000, 50_000] {
            let vectors = generate_clustered_vectors(n, dim, (n as f64).sqrt() as usize);
            let ids: Vec<i64> = (0..n as i64).collect();

            let num_queries = 500.min(n);
            let recall_queries = 50.min(n);

            // Build HNSW
            let hnsw_config = DescartesConfig::new(dim)
                .with_m(32)
                .with_ef_construction(200)
                .with_ef_search(80);

            let start = Instant::now();
            let mut hnsw = DescartesIndex::new(hnsw_config);
            hnsw.build_with_ids(&vectors, &ids);
            let hnsw_build = start.elapsed().as_secs_f64();

            // Build IVF
            let nlist = ((n as f64).sqrt() as usize).max(16).min(256);
            let nprobe = (nlist / 4).max(4);
            let ivf_config = IvfConfig::new(dim)
                .with_nlist(nlist)
                .with_nprobe(nprobe);

            let start = Instant::now();
            let mut ivf = IvfIndex::new(ivf_config);
            ivf.build(&vectors, &ids);
            let ivf_build = start.elapsed().as_secs_f64();

            // Warmup
            for i in 0..50.min(n) {
                let _ = hnsw.search(&vectors[i], k);
                let _ = ivf.search(&vectors[i], k);
            }

            // Measure HNSW QPS
            let start = Instant::now();
            for i in 0..num_queries {
                let _ = hnsw.search(&vectors[i % n], k);
            }
            let hnsw_qps = num_queries as f64 / start.elapsed().as_secs_f64();

            // Measure IVF QPS
            let start = Instant::now();
            for i in 0..num_queries {
                let _ = ivf.search(&vectors[i % n], k);
            }
            let ivf_qps = num_queries as f64 / start.elapsed().as_secs_f64();

            // Measure recall
            let mut hnsw_recall = 0.0;
            let mut ivf_recall = 0.0;
            for i in 0..recall_queries {
                let gt = compute_ground_truth(&vectors, &vectors[i], k);
                hnsw_recall += compute_recall(&gt, &hnsw.search(&vectors[i], k), k);
                ivf_recall += compute_recall(&gt, &ivf.search(&vectors[i], k), k);
            }
            hnsw_recall /= recall_queries as f64;
            ivf_recall /= recall_queries as f64;

            println!("{:>10} {:>12.0} {:>12.0} {:>11.1}% {:>11.1}% {:>9.2}s {:>9.2}s",
                format_num(n), hnsw_qps, ivf_qps, hnsw_recall * 100.0, ivf_recall * 100.0,
                hnsw_build, ivf_build);
        }
    }

    fn format_num(n: usize) -> String {
        if n >= 1_000_000 { format!("{}M", n / 1_000_000) }
        else if n >= 1_000 { format!("{}K", n / 1_000) }
        else { format!("{}", n) }
    }

    #[test]
    fn test_100k_512d() {
        let n = 100_000;
        let dim = 512;
        let k = 10;
        let num_queries = 200;
        let recall_queries = 30;

        println!("\n{}", "=".repeat(60));
        println!("100K × 512D: HNSW vs IVF");
        println!("{}\n", "=".repeat(60));

        let vectors = generate_clustered_vectors(n, dim, 100);
        let ids: Vec<i64> = (0..n as i64).collect();

        // Build HNSW
        println!("Building HNSW...");
        let hnsw_config = DescartesConfig::new(dim)
            .with_m(32)
            .with_ef_construction(200)
            .with_ef_search(80);

        let start = Instant::now();
        let mut hnsw = DescartesIndex::new(hnsw_config);
        hnsw.build_with_ids(&vectors, &ids);
        let hnsw_build = start.elapsed().as_secs_f64();
        println!("  HNSW build: {:.1}s", hnsw_build);

        // Build IVF
        println!("Building IVF...");
        let ivf_config = IvfConfig::new(dim)
            .with_nlist(256)
            .with_nprobe(24);

        let start = Instant::now();
        let mut ivf = IvfIndex::new(ivf_config);
        ivf.build(&vectors, &ids);
        let ivf_build = start.elapsed().as_secs_f64();
        println!("  IVF build: {:.1}s", ivf_build);

        // Warmup
        for i in 0..20 {
            let _ = hnsw.search(&vectors[i], k);
            let _ = ivf.search(&vectors[i], k);
        }

        // Measure HNSW
        println!("Benchmarking HNSW...");
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = hnsw.search(&vectors[i % n], k);
        }
        let hnsw_qps = num_queries as f64 / start.elapsed().as_secs_f64();

        // Measure IVF
        println!("Benchmarking IVF...");
        let start = Instant::now();
        for i in 0..num_queries {
            let _ = ivf.search(&vectors[i % n], k);
        }
        let ivf_qps = num_queries as f64 / start.elapsed().as_secs_f64();

        // Recall
        println!("Measuring recall...");
        let mut hnsw_recall = 0.0;
        let mut ivf_recall = 0.0;
        for i in 0..recall_queries {
            let gt = compute_ground_truth(&vectors, &vectors[i], k);
            hnsw_recall += compute_recall(&gt, &hnsw.search(&vectors[i], k), k);
            ivf_recall += compute_recall(&gt, &ivf.search(&vectors[i], k), k);
        }
        hnsw_recall /= recall_queries as f64;
        ivf_recall /= recall_queries as f64;

        println!("\n{}", "=".repeat(60));
        println!("RESULTS: 100K × 512D");
        println!("{}", "=".repeat(60));
        println!("{:>12} {:>12} {:>12} {:>12}", "", "HNSW", "IVF", "Winner");
        println!("{:-<50}", "");

        let qps_winner = if hnsw_qps > ivf_qps { "HNSW" } else { "IVF" };
        let build_winner = if hnsw_build < ivf_build { "HNSW" } else { "IVF" };
        let recall_winner = if hnsw_recall > ivf_recall { "HNSW" } else if ivf_recall > hnsw_recall { "IVF" } else { "TIE" };

        println!("{:>12} {:>12.0} {:>12.0} {:>12}", "QPS", hnsw_qps, ivf_qps, qps_winner);
        println!("{:>12} {:>11.1}% {:>11.1}% {:>12}", "Recall", hnsw_recall * 100.0, ivf_recall * 100.0, recall_winner);
        println!("{:>12} {:>11.1}s {:>11.1}s {:>12}", "Build", hnsw_build, ivf_build, build_winner);
        println!("{:>12} {:>11.1}MB {:>11.1}MB {:>12}", "Memory",
            hnsw.memory_usage() as f64 / 1e6,
            ivf.memory_usage() as f64 / 1e6,
            if hnsw.memory_usage() < ivf.memory_usage() { "HNSW" } else { "IVF" });

        let speedup = hnsw_qps / ivf_qps;
        println!("\n** HNSW is {:.1}x faster for search **", speedup);
        println!("** IVF builds {:.0}x faster **", hnsw_build / ivf_build);
    }
}
