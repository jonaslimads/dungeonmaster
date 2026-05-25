from pathlib import Path


class AudioService:
    @staticmethod
    def ensure_dirs(input_dir: Path, output_dir: Path) -> None:
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
