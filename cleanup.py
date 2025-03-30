import os
import shutil
import tempfile
import glob
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cleanup_cache_and_temp():
    """
    Clean up cache and temporary files while preserving database and TensorFlow learning data.
    """
    try:
        # Get the workspace directory
        workspace_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Files and directories to preserve
        preserve_patterns = [
            '*.db',  # Database files
            'telemetry.db',  # Telemetry database
            'models/*',  # TensorFlow models
            '*.gguf',  # GGUF model files
            '*.h5',  # Keras model files
            '*.pb',  # Protocol buffer files
            '*.pkl',  # Pickle files (model data)
            '*.npy',  # NumPy array files
            '*.npz',  # Compressed NumPy array files
            'config.json',  # Configuration file
            '*.log'  # Log files
        ]
        
        # Directories to clean
        cleanup_dirs = [
            tempfile.gettempdir(),  # System temp directory
            os.path.join(workspace_dir, '__pycache__'),  # Python cache
            os.path.join(workspace_dir, '.pytest_cache'),  # Pytest cache
            os.path.join(workspace_dir, '.coverage'),  # Coverage cache
            os.path.join(workspace_dir, '.mypy_cache'),  # MyPy cache
            os.path.join(workspace_dir, '.ruff_cache'),  # Ruff cache
            os.path.join(workspace_dir, '.hypothesis'),  # Hypothesis cache
            os.path.join(workspace_dir, '.tox'),  # Tox cache
            os.path.join(workspace_dir, '.eggs'),  # Eggs cache
            os.path.join(workspace_dir, 'build'),  # Build directory
            os.path.join(workspace_dir, 'dist'),  # Distribution directory
            os.path.join(workspace_dir, '*.egg-info'),  # Egg info directories
            os.path.join(workspace_dir, '.ipynb_checkpoints'),  # Jupyter checkpoints
            os.path.join(workspace_dir, '.DS_Store'),  # macOS system files
            os.path.join(workspace_dir, 'Thumbs.db'),  # Windows thumbnail cache
        ]
        
        # Clean up directories
        for dir_pattern in cleanup_dirs:
            for dir_path in glob.glob(dir_pattern):
                if os.path.exists(dir_path):
                    try:
                        if os.path.isdir(dir_path):
                            shutil.rmtree(dir_path)
                            logger.info(f"Removed directory: {dir_path}")
                        else:
                            os.remove(dir_path)
                            logger.info(f"Removed file: {dir_path}")
                    except Exception as e:
                        logger.error(f"Error removing {dir_path}: {str(e)}")
        
        # Clean up Python cache files
        for root, dirs, files in os.walk(workspace_dir):
            # Remove __pycache__ directories
            if '__pycache__' in dirs:
                pycache_dir = os.path.join(root, '__pycache__')
                try:
                    shutil.rmtree(pycache_dir)
                    logger.info(f"Removed Python cache directory: {pycache_dir}")
                except Exception as e:
                    logger.error(f"Error removing Python cache directory {pycache_dir}: {str(e)}")
            
            # Remove .pyc files
            for file in files:
                if file.endswith('.pyc'):
                    pyc_file = os.path.join(root, file)
                    try:
                        os.remove(pyc_file)
                        logger.info(f"Removed Python compiled file: {pyc_file}")
                    except Exception as e:
                        logger.error(f"Error removing Python compiled file {pyc_file}: {str(e)}")
        
        # Clean up TensorFlow specific temporary files
        tf_temp_dirs = [
            os.path.join(workspace_dir, '.tensorflow'),
            os.path.join(tempfile.gettempdir(), 'tensorflow'),
            os.path.join(tempfile.gettempdir(), 'tf_*'),
        ]
        
        for tf_dir in tf_temp_dirs:
            if os.path.exists(tf_dir):
                try:
                    shutil.rmtree(tf_dir)
                    logger.info(f"Removed TensorFlow temporary directory: {tf_dir}")
                except Exception as e:
                    logger.error(f"Error removing TensorFlow temporary directory {tf_dir}: {str(e)}")
        
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise

if __name__ == "__main__":
    cleanup_cache_and_temp()