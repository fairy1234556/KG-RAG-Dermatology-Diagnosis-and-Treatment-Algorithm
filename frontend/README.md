# 前端演示工程

本目录为“基于知识图谱增强的皮肤病智能辅助诊疗系统 V1.0”第二阶段前端。

## 技术栈

- Vue 3
- TypeScript
- Vite
- Element Plus
- Pinia
- Axios
- Vitest

## 能力范围

已实现：

- 中文角色入口。
- 中文医生工作台。
- 中文患者健康咨询页。
- 中文知识图谱查询页。
- 中文 KG-RAG 辅助解释页。
- 对接第一阶段后端 `/api` 接口。
- 证据链卡片展示：候选疾病 -> 图谱关系 -> 证据文本 -> 医学来源。

暂未接入：

- 账号密码登录和权限数据库。
- 真实病例保存。
- 医生审核流程。
- 真实大模型调用。
- 图像分类和 Grad-CAM。
- 自动一致性校验和实验指标。

## 运行

先启动后端：

```bash
uvicorn backend.app.main:app --reload
```

再启动前端：

```bash
cd frontend
npm install
npm run dev
```

Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 构建与测试

```bash
cd frontend
npm run build
npm run test
```

本阶段所有界面默认使用简体中文。医学提示固定显示：

```text
本系统结果仅用于辅助决策和健康信息参考，不替代医生面诊、皮肤镜检查及病理诊断。
```

