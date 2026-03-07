# inf-Astronomical-Observation

宇宙観測の査読論文コーパスを保管する inf-Memory カテゴリ。

## 目的

- peer-reviewed astronomical / cosmological observation papers を集約する
- raw / normalized / indexed / projection を分離する
- 後続の inf-Brain / inf-Model / Katala GUT 検討で、観測論文の由来と加工段階を追えるようにする

## 構造

- `raw/` : DOI harvest の生データ
- `normalized/` : timeline normalization 後のデータ
- `indexed/` : genre index などの索引
- `projections/` : latest-by-genre や inf-theory projection
- `curated/` : 今後の人手検証・精査済みセット
- `manifests/` : state / manifest / inventory

## 現状

このカテゴリは既存の `inf-Coding-Assist` 側出力を壊さずに、
**inf-Memory の保存カテゴリとして再配置した複製**を先に置いている。

将来的には、新規 harvest / normalize / index / projection 系ジョブもこのカテゴリを正式保存先として参照・出力する想定。
