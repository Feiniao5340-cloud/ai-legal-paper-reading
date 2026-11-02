# AI法学文献两阶段阅读实践

以刘宏宇《我国自动驾驶汽车保险制度的立法审视与完善进路》为例：先用AI建立文章主线，再围绕实际疑点回查主体、义务、条件和位置，最后检查补充解释是否超出原文。

- [技术分享正文](docs/技术分享.md)
- [单命令复现步骤](reproduction/复现步骤.md)
- [随包原文片段](evidence/case-source.txt)
- [已跑通的片段阅读结果](examples/self-contained/answer.md)
- [片段案例核查](evidence/自包含案例核查.md)
- [玻尔首问结果](examples/bohrium/首次回答-页面转录.md)、[实际追问结果](examples/bohrium/追问回答-页面转录.md)及[闭环核查](evidence/玻尔闭环核查.md)
- [既有无Skill完整结果](examples/without-skill/answer-original.txt)、[有Skill完整结果](examples/with-skill/answer-original.txt)及[源文核查](evidence/核查记录.md)
- [冻结Skill](skill/SKILL.md)与[来源贡献](ATTRIBUTION.md)

```text
python -X utf8 reproduction/run_case.py --source evidence/case-source.txt --out ../reading-run --codex codex --model gpt-6-luna --reasoning max
```

材料自包含，读者无需另下载整篇论文即可完成片段练习；模型调用仍需自己的账号、权限和网络。默认由本地脚本准备文字，模型直接阅读，不需要模型执行命令。

三类证据分别解释：旧全文两臂是单组非盲事后观察；玻尔追问是读者提供方向后的修复；新增片段入口是真实运行验证，不是全文对照或稳定增益证明。原始失败与输出保留，论文全文不公开，法规未另行联网核实。历史Skill93.75分与技术分享首版84分均不能当本版成绩。
