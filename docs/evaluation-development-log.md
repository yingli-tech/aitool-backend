# Evaluation Feature Development Log

## Step 1 — Problem Definition

### 1. Current System
What does the current recommendation system do?
现在推荐系统的工作过程是这样的,用户输入一个query,是自然语言写的,然后大模型来解析,把它转化成一个结构化的条件,再根据这个条件去数据库里面来找符合条件的工具。那如果这个筛选里面没有得到结果,就会使用fallback流程,放松一个限制条件,再做取回。如果获得了候选工具的话,再对这个候选工具进行打分和排序。

### 2. Current Problem
What can I currently NOT know or verify about the system?
不知道哪个工具会被推荐出来。要是拿着数据库里面的数据,如果给到我一个结果,我可以人工地去检查,看它是不是符合条件,是什么,然后再根据那个条件一路看,它的打分是不是正确。这个是可以做的。但非常地繁琐,要挨个检查的话,挨个做的话就挺困难。

### 3. Why It Matters
Why is this a problem?
在这个系统，输入一个query,会返回推荐的工具。这个时候呢,是可以人工地去核对这个结果，检查里面每个过程,比如看是不是过滤正确的,是不是打分正确的。这些可以挨个做,但它的问题是什么呢?只能说是检查一些,人工地检查一些例子来看这个系统,有没有正常工作。系统有没有按照每一个模块,不管是parser,还是filter,还是fallback,ranking的过程,它有没有按照我预设的逻辑去做。比如用一些相似的queries输入进系统里,根据它们的细微的差异来观察系统的行为。但这样的观察，样本很少。之后数据库会增加更多的工具，人工检查过于费时费力。总之，那我其实是想了解这个系统有按照预期在工作。我需要一些明确指标，但我不知道选择哪些。

### 4. Goal
What should the evaluation feature allow me to understand?
每一次输入一个query，给出的推荐结果，首先是确定系统是不是按照预期工作的,推荐的工具准不准确。换言之，我的目标是想看这套推荐逻辑,在系统里是否正确执行，执行之后是否能够推荐出正确的东西,但我不知道要怎么去定义正确这件事情。并且我意识到不是要最准确的,特别精确的百分百啊,而是说是一个尽量高的相关性。还有一个目标是想要能做出一个baseline。之后不管在哪一个模块里面做扩展或增强,可以通过这样的baseline来观测，判断扩展或增加的部分对结果是什么样的影响。

### LLM Review
你的 Problem Definition 目前包含三个潜在目标：

A. Implementation correctness — pipeline 是否按照设计工作
B. Recommendation quality — 推荐结果是否真正 relevant
C. Change measurement — 建立 baseline，衡量未来修改带来的影响

### My Analysis of the Review
我认为潜在目标：

A. Implementation correctness and transparency— pipeline 是否按照设计工作, 并可观测
B. Recommendation quality — 推荐结果是否真正 relevant
C. Change measurement — 建立 baseline，衡量未来修改带来的影响
D. 自动生成测试样本、自动执行验证、给出评估结果

重要性是 B = A > C > D

### Final Problem Definition

The current recommendation system can generate recommendations through a
parse → filter → fallback → rank pipeline, but it does not have a systematic
evaluation mechanism.

Currently, I can manually inspect individual queries and verify whether each
stage of the pipeline behaves according to the designed logic. However, this
process is time-consuming, difficult to scale, and limited to a small number
of manually selected examples.

More importantly, even if each component behaves according to its
implementation, I do not yet have a clear and measurable definition of
recommendation quality. In particular, I need to determine whether the
recommended tools are sufficiently relevant to the user's actual needs.

Therefore, the evaluation feature should primarily solve three problems:

1. **Implementation correctness and transparency**
   - Determine whether parser, filter, fallback, and ranking behave as
     designed.
   - Make intermediate behavior observable so failures can be traced to
     specific stages.

2. **Recommendation quality**
   - Define what constitutes a good/relevant recommendation.
   - Systematically evaluate recommendation quality across more than a small
     set of manually inspected queries.

3. **Change measurement**
   - Establish a reproducible baseline for the current system.
   - Allow future changes to parser, filter, fallback, or ranking logic to be
     compared against that baseline.

Current priority:

**Recommendation Quality = Implementation Correctness & Transparency >
Change Measurement**

Potential requirement to explore later:
Automate test-case generation, evaluation execution, and evaluation reporting.