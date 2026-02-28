"""
KS30b Stage Store — External Memory for Pipeline Stages

設計根拠:
  LLMのコンテキスト内「記憶」は圧縮で歪む。
  各ステージの出力をJSONファイルに外部化することで:
  1. 後段が前段の出力を正確に参照できる（記憶違い防止）
  2. パイプライン全体の再現可能性が向上
  3. デバッグ時に各段の出力を個別検証できる
  4. 異なるLLM/モデルで同じ入力を再実行して比較できる

  参考: DDSP (Engel et al., 2020) の設計思想
  — 各モジュールの出力を明示的にパラメータ化する

Usage:
  store = StageStore("run_2026-02-28_05-23")
  store.write("S02", {"key_concepts": [...], "propositions": {...}})
  s2_out = store.read("S02")  # 正確な参照、記憶に頼らない
  store.finalize()  # メタデータ書き込み
"""

import json
import os
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class StageStore:
    """Immutable stage output store with integrity verification."""

    def __init__(self, run_id: Optional[str] = None, base_dir: Optional[str] = None):
        if run_id is None:
            run_id = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
        if base_dir is None:
            base_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "runs"
            )
        self.run_id = run_id
        self.run_dir = os.path.join(base_dir, run_id)
        os.makedirs(self.run_dir, exist_ok=True)
        self._meta = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stages": {},
            "integrity": {},
        }

    def write(self, stage_name: str, data: Any, metadata: Optional[Dict] = None) -> str:
        """Write stage output. Returns content hash. Immutable per run."""
        if stage_name in self._meta["stages"]:
            raise ValueError(
                f"Stage '{stage_name}' already written in run '{self.run_id}'. "
                f"Immutable. Start a new run for re-execution."
            )
        payload = {
            "stage": stage_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
            "metadata": metadata or {},
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        filepath = os.path.join(self.run_dir, f"{stage_name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self._meta["stages"][stage_name] = {
            "file": f"{stage_name}.json",
            "written_at": payload["timestamp"],
            "hash": content_hash,
        }
        self._meta["integrity"][stage_name] = content_hash
        return content_hash

    def read(self, stage_name: str, verify: bool = True) -> Any:
        """Read stage output. Verifies integrity by default.
        This is the ONLY correct way to reference a previous stage's output.
        Never rely on LLM context/memory for cross-stage data.
        """
        filepath = os.path.join(self.run_dir, f"{stage_name}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(
                f"Stage '{stage_name}' not found in run '{self.run_id}'. "
                f"Available: {list(self._meta['stages'].keys())}"
            )
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if verify and stage_name in self._meta["integrity"]:
            actual_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            expected_hash = self._meta["integrity"][stage_name]
            if actual_hash != expected_hash:
                raise IntegrityError(
                    f"Stage '{stage_name}' integrity failed. "
                    f"Expected {expected_hash}, got {actual_hash}."
                )
        return json.loads(content)["data"]

    def read_field(self, stage_name: str, field: str, default: Any = None) -> Any:
        """Read a specific field from a stage's output."""
        data = self.read(stage_name)
        if isinstance(data, dict):
            return data.get(field, default)
        return default

    def has_stage(self, stage_name: str) -> bool:
        return stage_name in self._meta["stages"]

    def list_stages(self) -> List[str]:
        return list(self._meta["stages"].keys())

    def diff(self, stage_name: str, other_store: "StageStore") -> Dict:
        """Compare a stage between two runs."""
        my_data = self.read(stage_name)
        other_data = other_store.read(stage_name)
        my_hash = self._meta["integrity"].get(stage_name, "?")
        other_hash = other_store._meta["integrity"].get(stage_name, "?")
        return {
            "stage": stage_name,
            "run_a": self.run_id, "run_b": other_store.run_id,
            "hash_match": my_hash == other_hash,
            "hash_a": my_hash, "hash_b": other_hash,
            "data_a": my_data, "data_b": other_data,
        }

    def finalize(self) -> str:
        """Write run metadata after all stages complete."""
        self._meta["finalized_at"] = datetime.now(timezone.utc).isoformat()
        self._meta["total_stages"] = len(self._meta["stages"])
        meta_path = os.path.join(self.run_dir, "_meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self._meta, f, ensure_ascii=False, indent=2)
        return meta_path

    @classmethod
    def load(cls, run_id: str, base_dir: Optional[str] = None) -> "StageStore":
        """Load an existing run."""
        store = cls(run_id=run_id, base_dir=base_dir)
        meta_path = os.path.join(store.run_dir, "_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                store._meta = json.load(f)
        else:
            for fname in sorted(os.listdir(store.run_dir)):
                if fname.startswith("_") or not fname.endswith(".json"):
                    continue
                stage_name = fname.replace(".json", "")
                filepath = os.path.join(store.run_dir, fname)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                h = hashlib.sha256(content.encode()).hexdigest()[:16]
                store._meta["stages"][stage_name] = {"file": fname, "hash": h}
                store._meta["integrity"][stage_name] = h
        return store


class IntegrityError(Exception):
    """Raised when stage output integrity check fails."""
    pass
