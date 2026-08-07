# Local Setup

Status: Current.

## KaggleHub Authentication

This project uses KaggleHub Option 3 authentication for Kaggle dataset access.

1. Generate a Kaggle API token from Kaggle account settings.
2. Save the token value at:

   ```bash
   ~/.kaggle/access_token
   ```

3. Never commit this token file.
4. Do not place the token under the project directory.

The token file is private local machine state. The project only checks that the file exists before attempting a KaggleHub download.

## Dataset Download

After creating a virtual environment and installing dependencies, run:

```bash
python scripts/download_kagglehub_f1_data.py
```

The script downloads `patelris/formula-1-complete-dataset-1950-2026` into:

```bash
data/raw/f1_complete_dataset/
```

Downloaded raw data is ignored by Git.
