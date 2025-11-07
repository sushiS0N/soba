import os
import usd_io, engine


def analyze_solar_scene(usd_path, output_path=None):
    """
    Complete solar analysis pipeline

    Args:
        usd_path: Path to input USD file
        output_path: Path for output USD (optional, defaults to input_results.usda)

    Returns:
        numpy array of results
    """
    print("=" * 70)
    print("SOLAR ANALYSIS PIPELINE")
    print("=" * 70)
    print()

    # Step 1: Read USD
    print(f"\nStep 1: Reading USD file {usd_path}")

    try:
        scene_data = usd_io.read_solar_usd(usd_path)
        scene_data["usd_path"] = usd_path  # Store for EPW path resolution
        print(f"  Loaded {len(scene_data['target']['face_centers'])} faces")
        print(f"  Loaded {len(scene_data['context'])} triangles")
    except Exception as e:
        print(f" Failed to read USD: {e}")
        import traceback

        traceback.print_exc()
        return None

    # Step 2: Run analysis
    print("\nStep 2: Running analysis...")
    try:
        optix_module = engine.setup_optix_module()
        results = engine.run_optix_analysis(scene_data, optix_module)
    except Exception as e:
        print(f" Analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return None

    # Step 3: Write results (TODO)
    print("\nStep 3: Writing results to USD...")
    if output_path is None:
        base = os.path.splitext(usd_path)[0]
        output_path = f"{base}_results.usda"
        csv_path = f"{base}_results.csv"

    usd_io.write_results_to_usd(usd_path, results, output_usd_path=None)
    usd_io.write_results_csv(csv_path, results)
    print(f"    Saved USD to: {output_path}")
    print(f"    Saved CSV to: {output_path}")

    print("\n" + "=" * 70)
    print("🎉 PIPELINE COMPLETE!")
    print("=" * 70)
    
    return output_path


if __name__ == "__main__":
    # Test the pipeline
    usd_path = r"C:/Users/wTxT/Documents/maya/2025/scripts/SolarAnalysis/temp/solar_analysis.usda"
    results = analyze_solar_scene(usd_path)
