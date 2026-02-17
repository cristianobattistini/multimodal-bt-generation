import os
import subprocess

# List of datasets to download based on out_temp content minus the exclusion list
DATASETS_TO_DOWNLOAD = [
    'asu_table_top_converted_externally_to_rlds',
    'austin_buds_dataset_converted_externally_to_rlds',
    'cmu_stretch',
    'columbia_cairlab_pusht_real',
    'utokyo_pr2_opening_fridge_converted_externally_to_rlds',
    'utokyo_pr2_tabletop_manipulation_converted_externally_to_rlds'
]

# Destination directory (standard tfds location)
BASE_DOWNLOAD_DIR = os.path.expanduser('~/tensorflow_datasets')

def get_dataset_info(dataset_name):
  if dataset_name == 'robo_net':
    version = '1.0.0'
  elif dataset_name == 'language_table':
    version = '0.0.1'
  else:
    version = '0.1.0'
  
  gcs_uri = f'gs://gresearch/robotics/{dataset_name}/{version}'
  return version, gcs_uri

print(f"Starting download for {len(DATASETS_TO_DOWNLOAD)} datasets to {BASE_DOWNLOAD_DIR}...")

for dataset_name in DATASETS_TO_DOWNLOAD:
    print(f"\nProcessing {dataset_name}...")
    
    version, gcs_uri = get_dataset_info(dataset_name)
    local_dataset_dir = os.path.join(BASE_DOWNLOAD_DIR, dataset_name)
    
    # Check if already exists
    local_version_dir = os.path.join(local_dataset_dir, version)
    if os.path.exists(local_version_dir):
        print(f"  Directory {local_version_dir} already exists. Skipping.")
        continue

    # Create parent directory
    os.makedirs(local_dataset_dir, exist_ok=True)
    
    print(f"  Downloading from {gcs_uri} to {local_dataset_dir}...")
    
    # Use gsutil to copy recursively
    # gsutil cp -r gs://.../0.1.0 /local/path/dataset_name/
    # This creates /local/path/dataset_name/0.1.0
    cmd = ['gsutil', 'cp', '-r', gcs_uri, local_dataset_dir]
    
    try:
        subprocess.check_call(cmd)
        print(f"  Successfully downloaded {dataset_name}")
    except subprocess.CalledProcessError as e:
        print(f"  Error downloading {dataset_name}: {e}")

print("\nAll operations completed.")