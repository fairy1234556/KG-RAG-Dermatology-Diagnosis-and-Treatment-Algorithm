# HAM10000 皮肤病知识图谱查询 Demo

## 数据文件

- `csv/entity_nodes.csv`
- `csv/triples.csv`
- `csv/source_references.csv`

## 脚本文件

- `kg_query_demo.py`

## 已实现功能

- `query_by_disease`：按疾病查询全部证据三元组
- `query_by_relation`：按疾病和关系类型查询证据
- `query_by_feature`：按皮损特征反查相关疾病

## 运行命令

```bash
python kg/kg_query_demo.py
```

## 测试示例

- `query_by_disease("黑色素瘤")`
- `query_by_relation("基底细胞癌", "has_manifestation")`
- `query_by_feature("珍珠样结节")`

## 说明

当前版本暂未接入 Neo4j 和 LLM，先基于 CSV 实现最小图谱路径检索能力，为后续 KG-RAG 提供证据链召回基础。
