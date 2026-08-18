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

- 关于目标A，新增可观测
- 新增：D. 自动生成测试样本、自动执行验证、给出评估结果
- 新增：重要性是 B = A > C > D

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


## Step 2 — Requirements Definition

### My Initial Requirements

#### 1. Recommendation Quality
What information do I need in order to determine whether the recommendations
are good for a user's query?

我需要知道用户提出来的需求里面,对应的结构化内容,这个推荐工具按照用户的query表达出来的需求，满足需求的程度。

#### 2. Pipeline Correctness & Transparency
What do I need to observe or verify for each stage:
- Parser
- Filter
- Fallback
- Ranking

在parser部分,要看json结构是不是正确的,字段是不是正确的,字段里的类型是不是正确的。当parser出来的标签,如果不是数据库里面的标签,是新的标签的话,这里面对应的,比如不管是function还是use case,是否包含已在数据库里的内容。fallback要看fallback的次序对不对,还有是否触发,是否每次都有触发fallback,当fallback的条件被满足之后,也就是没有工具之后。ranking是否对所有的候选工具都做了ranking?并且他做出来的ranking也是符合这个打分机制的。

#### 3. Change Measurement
What should I be able to compare before and after changing the system?

我想知道如果改变了系统,推荐的结果相关性提高,还是降低?还有它每个模块是否正常工作的?

#### 4. Evaluation Operation
How do I expect to use this evaluation system in practice?

我需要它能在这个内容上线之前就做好这样的评估。并不是在用户实时输入query的时候,它会自动产生评估,而是在给用户用之前,先确认这个系统运行得如何


### LLM Review

The initial requirements can be grouped into:

A. Recommendation Quality
- Evaluate how well recommended tools satisfy the needs expressed in the
  user's query.

B. Pipeline Correctness & Transparency
- Parser: validate schema, fields, data types, and handling/mapping of labels
  not currently represented in the database.
- Filter: verify that retained tools satisfy parsed constraints and that valid
  candidates are not incorrectly excluded.
- Fallback: verify trigger conditions and relaxation order.
- Ranking: verify all candidates are scored and that scores/ranking follow the
  designed ranking logic.

C. Change Measurement
- Measure whether recommendation relevance improves or regresses after system
  changes.
- Detect regressions in individual pipeline components.

D. Evaluation Operation
- Evaluation should run offline before release rather than on every production
  user request.

Potential missing requirement:

E. Reproducibility
- A stable evaluation set is needed so different versions of the system can be
  compared against the same cases.


### My Analysis of the Review

- 去掉在parser阶段handling new labels的需求。
- filter部分确实需要验证筛选结果是否真的符合parsed constraints，以及有没有错误排除本该保留的工具。
- 同意把Reproducibility加入要求，应该保留足够的固定测试集，用于每次改动前后比较。
- 新增：输入同一测试query在同一系统时，观测中间部分（不同stages）的输出是否稳定，最终输出结果是否稳定。


### Final Requirements

The evaluation feature should support offline, reproducible evaluation of both
recommendation quality and pipeline correctness before changes are released.

#### 1. Recommendation Quality

The evaluation should determine how well the final recommended tools satisfy
the needs expressed in the user's natural-language query.

It should provide a systematic way to assess recommendation relevance rather
than relying only on manual inspection of a small number of examples.

#### 2. Pipeline Correctness and Transparency

The evaluation should make the intermediate behavior of the recommendation
pipeline observable and verify that each stage behaves according to its
designed logic.

##### Parser
- Verify that the parser output follows the expected JSON structure.
- Verify that required fields are present and correct.
- Verify that field values use the expected data types.

##### Filter
- Verify that retained candidate tools satisfy the parsed constraints.
- Verify that tools which should satisfy the constraints are not incorrectly
  excluded.

##### Fallback
- Verify that fallback is triggered when the normal filtering process returns
  no candidates.
- Verify that fallback is not triggered when its trigger condition is not met.
- Verify that constraint relaxation follows the designed fallback order.

##### Ranking
- Verify that all candidate tools are included in the ranking process.
- Verify that ranking scores are calculated according to the designed scoring
  mechanism.
- Verify that the final ordering is consistent with the calculated scores.

#### 3. Change Measurement

The evaluation should establish a baseline for the current system.

After changes are made to the parser, filter, fallback, ranking logic, or other
parts of the recommendation pipeline, the same evaluation process should be
used to determine:

- whether recommendation relevance improved or regressed;
- whether any pipeline component developed a correctness regression.

#### 4. Reproducibility and Stability

The evaluation should maintain a sufficiently large and stable set of test
queries so that different versions of the system can be evaluated against the
same cases.

For the same test query on the same system version, the evaluation should also
observe whether:

- intermediate outputs from different pipeline stages remain stable;
- final recommendation results remain stable.

This allows unexpected nondeterministic behavior to be identified separately
from intentional system changes.

#### 5. Evaluation Operation

The evaluation should operate as an offline, pre-release process.

It is not intended to evaluate every production user request in real time.

The expected workflow is:

System change
→ Run evaluation suite
→ Inspect recommendation quality and pipeline correctness
→ Compare results with the existing baseline
→ Decide whether the change is acceptable for release


## Step 3 — Existing System Analysis

### Current Pipeline

Query
→ Parser
→ Filter
→ Fallback (if needed)
→ Ranking
→ Top Results
→ Response

### Parser

Input:
- Validated natural-language query
- Current taxonomy context from the database

Output:
- Normalized structured `parsed_query`

Currently observable:
- Final normalized `parsed_query` is exposed in the API response and request log.

Missing / limitations for evaluation:
- Raw LLM output and prompt are not preserved.
- Pre-normalization vs. post-normalization output is not observable.
- Parser behavior depends on the current database taxonomy.
- Parser requires a live LLM call, so repeated runs may not be deterministic.

### Filter

Input:
- Normalized `parsed_query`
- Current database contents

Output:
- Candidate tools matching the active constraints

Currently observable:
- Final candidate results eventually flow into later stages.

Missing / limitations for evaluation:
- Candidate sets after each filtering constraint are not exposed.
- The system does not record which constraint eliminated which tools.
- The strict-filter candidate count before fallback is not preserved.
- When filtering returns no result, the cause of the empty set is not directly observable.

### Fallback

Input:
- Original normalized `parsed_query`
- Database contents

Output:
- Candidate tools after relaxation
- `fallback_info`
- Relaxed `active_query`

Currently observable:
- Fallback usage
- Relaxed fields
- Retry count
- Retry history
- Constraint snapshots

Missing / limitations for evaluation:
- Candidate identities from individual retry attempts are not preserved.
- Strict-filter candidate count before fallback is not explicitly stored.
- The final `active_query` used after successful fallback is not exposed in the final response.

### Ranking

Input:
- Candidate tools
- Active query, which may contain relaxed constraints

Output:
- Scored and ranked candidates
- Top 3 results

Currently observable:
- Final scores
- Rank
- Match-count breakdowns for returned tools

Missing / limitations for evaluation:
- Full ranked candidate list is discarded after top-3 truncation.
- Detailed per-candidate scoring decisions are not persisted.
- Ranking may use a relaxed `active_query`, while the response still exposes the original `parsed_query`.

### Final Recommendation Output

Currently observable:
- Original query
- Original normalized `parsed_query`
- Fallback metadata
- Result count
- Top ranked results
- Ranking score and match-count breakdown

Missing / limitations for evaluation:
- Full candidate universe is unavailable.
- Final `active_query` after fallback is unavailable.
- Stage-level intermediate states are not persisted.

### Existing Logging

Current request-level logging includes:
- timestamp
- query
- parsed_query
- fallback_info
- result_count
- error

Logging is currently request-level and print-based rather than a persisted
stage-by-stage evaluation artifact.

### Key Evaluation Gaps

Based on the evaluation requirements, the main gaps are:

1. Insufficient visibility into intermediate filter states.
2. No preservation of the full ranked candidate set.
3. No explicit final `active_query` after fallback.
4. Limited ability to replay or diagnose parser behavior.
5. No stable evaluation dataset or baseline currently exists.
6. No mechanism currently compares recommendation quality across system versions.


### My Analysis of the Codebase Review

The existing system already exposes enough information to inspect final
recommendations and most fallback behavior, so evaluation does not require
rebuilding the recommendation pipeline.

However, the current observability is insufficient for systematic
stage-level evaluation.

The most important missing information appears to be:
- intermediate filter candidate sets;
- the final active query after fallback;
- the full ranked candidate list before top-k truncation.

Parser stability should be evaluated from the first version. Because the LLM parser is the first potentially non-deterministic stage in the pipeline, instability introduced there can propagate through all downstream stages. 

The evaluation should therefore preserve the raw LLM output and parsed output for repeated runs of the same fixed queries, providing an initial observation point for tracing where instability is introduced.

Raw LLM outputs should also be replayable through the deterministic downstream stages, so that parser-induced variability can be separated from instability introduced by filtering, ranking, or other later deterministic processing.

Therefore, the evaluation design should reuse the existing pipeline where
possible and add only the observability needed to evaluate it.


## Step 4 — Solution Exploration

### Candidate Architecture Options

#### Option A — Deterministic Offline Evaluation Runner

Description:
- Uses a fixed evaluation dataset and a predefined evaluation workflow.
- Runs the recommendation pipeline offline.
- Captures stage-level outputs and applies deterministic correctness checks.
- Supports repeated execution, baseline comparison, and regression detection.

Strengths:
- Reproducible and easy to debug.
- Suitable for stage-level correctness evaluation.
- Can measure failure rates for parser, filter, fallback, and ranking.
- Can support replay of saved parser outputs through downstream deterministic stages.
- Appropriate for regression testing across system versions.

Limitations:
- Cannot fully judge semantic recommendation relevance.
- Requires explicit pass/fail criteria for each pipeline stage.
- Some additional observability must be added to the current pipeline.

Best suited for:
- Pipeline correctness.
- Regression testing.
- Stability measurement.
- Baseline comparison.


#### Option B — LLM-as-a-Judge Evaluation

Description:
- Uses an LLM to evaluate how well the final recommended tools satisfy the user's natural-language query.
- Operates as a semantic quality evaluation component rather than as the main evaluation workflow.

Strengths:
- Can evaluate recommendation relevance that deterministic checks cannot fully capture.
- Can assess whether a technically correct recommendation is actually useful for the user's expressed need.
- Can provide graded relevance scores rather than only binary pass/fail judgments.

Limitations:
- The judge itself may be nondeterministic.
- Results can depend on judge prompt design, model choice, and model version.
- Repeated judge runs may produce different scores.
- Adds additional latency and API cost.
- Judge stability must itself be measured.

Best suited for:
- Semantic recommendation relevance.
- Quality assessment of final recommendations.


#### Option C — Agent-Orchestrated Evaluation

Description:
- Uses an agent to dynamically decide which evaluation tools or checks to run based on intermediate evaluation results.
- The agent could potentially choose additional tests, rerun unstable cases, inspect failed stages, or perform root-cause investigation.

Strengths:
- Flexible when evaluation paths cannot be predetermined.
- Could automate deeper failure investigation.
- Could dynamically select evaluation tools based on observed failures.

Limitations:
- Adds orchestration complexity and additional nondeterminism.
- Harder to reproduce and debug.
- Not necessary when the evaluation workflow is already known in advance.
- Introduces complexity before reliable evaluation primitives have been established.

Best suited for:
- Future dynamic investigation.
- Automatic root-cause analysis.
- Evaluation workflows that require conditional tool selection.


### My Initial Preference

For the first version, I prefer a fixed offline evaluation pipeline rather
than an agent-orchestrated workflow.

The evaluation workflow is mostly predetermined, so dynamic orchestration is
not currently necessary.

The first version should focus on:
- measuring failure rates for each pipeline stage;
- identifying failed cases and their outputs;
- supporting reproducible and repeatable evaluation;
- measuring output stability across repeated runs;
- evaluating recommendation relevance separately from pipeline correctness.

I view the first-version evaluation as three complementary dimensions:

1. **Deterministic Pipeline Correctness Evaluation**
   - Checks whether parser, filter, fallback, and ranking behave according to
     their designed logic.
   - Measures stage-level failure rates.
   - Records failed cases for inspection.

2. **LLM-Based Recommendation Relevance Evaluation**
   - Evaluates how well the final recommended tools satisfy the user's query.
   - This semantic relevance cannot be fully determined by deterministic
     pipeline checks alone.

3. **Stability Evaluation**
   - Repeatedly runs the same fixed queries against the same system version.
   - Compares intermediate stage outputs and final recommendation outputs
     across repeated runs.
   - Quantifies how stable each stage is rather than only detecting that
     variation occurred.
   - Preserves raw LLM parser outputs so parser-induced variability can be
     distinguished from downstream behavior.
   - Replays fixed parser outputs through downstream deterministic stages to
     isolate where instability is introduced.


### Questions / Uncertainties

The following details still need to be defined in the detailed evaluation
design:

- What exactly constitutes a parser failure?
- What constitutes a filter, fallback, or ranking failure?
- How should stage-level failure rates be calculated?
- How should stability be measured?
- For parser output, should stability require exact normalized JSON equality,
  or can semantically equivalent outputs be considered stable?
- For final recommendations, should stability measure:
  - exact top-k equality;
  - overlap between recommended tools;
  - ranking-order consistency;
  - or a combination of these?
- How many repeated runs are needed to estimate stability?
- How should LLM-judge relevance scores be defined?
- How should the stability of the LLM judge itself be measured?
- What should be included in the fixed evaluation dataset?


### Final Architecture Decision

For V1, the evaluation system will use a fixed offline evaluation pipeline
rather than an agent.

The reason is that the evaluation workflow is predetermined and the primary
goal is reliable, reproducible measurement rather than dynamic investigation
or autonomous decision-making.

The V1 architecture will contain three complementary evaluation paths:

1. **Deterministic Pipeline Correctness Evaluation**
   - Evaluate parser, filter, fallback, and ranking correctness.
   - Capture required intermediate outputs.
   - Calculate stage-level failure rates.
   - Preserve failed cases for diagnosis.
   - Support regression testing and baseline comparison.

2. **LLM-Based Recommendation Relevance Evaluation**
   - Evaluate semantic relevance between user queries and final recommended
     tools.
   - Operate as a separate quality-evaluation component because recommendation
     relevance cannot be fully determined by deterministic pipeline checks.
   - Measure the consistency of the judge itself where repeated evaluation is
     required.

3. **Stability Evaluation**
   - Repeatedly execute the same fixed queries against the same system version.
   - Compare outputs at each pipeline stage across repeated runs.
   - Calculate stage-level stability metrics.
   - Measure final recommendation stability.
   - Preserve raw LLM parser outputs and normalized parsed outputs.
   - Replay fixed parser outputs through downstream deterministic stages so
     parser-induced variability can be separated from downstream behavior.

All three evaluation paths will operate on a stable offline evaluation dataset.

Their outputs will be combined into a common evaluation report containing:
- pipeline correctness results;
- stage-level failure rates;
- failed cases;
- recommendation relevance results;
- stage-level stability measurements;
- final-result stability measurements;
- comparison against the existing baseline.

Agent orchestration is intentionally excluded from V1.

It may be reconsidered later if the evaluation process requires:
- dynamic selection of evaluation tools;
- conditional investigation based on failures;
- automatic root-cause analysis;
- or other evaluation paths that cannot be predetermined.


## Step 5 — Detailed Evaluation Design

### 1. Evaluation Dataset Design

#### Core Principle

Each evaluation benchmark is bound to a specific database snapshot/version.

A benchmark therefore represents:

fixed test cases
+ fixed database state
+ defined expected behavior

System versions should only be compared against the same benchmark when the
database snapshot remains unchanged.

If the database changes materially, a new benchmark version should be created
and its expected outputs reviewed.

#### Test Case Inputs

Each test case stores:

- raw natural-language `query`;
- expected normalized parsed representation;
- test-case category metadata.

The same test case supports two execution modes:

1. End-to-end mode:
   query → parser → filter → fallback → ranking

2. Parser-replay mode:
   saved expected/observed parsed representation
   → filter → fallback → ranking

This allows parser-induced variability to be separated from downstream behavior.

#### Expected Parser Behavior

The expected parser output should represent all user intents that are clearly
expressed in the query.

Correctness should be checked field by field after normalization.

For fields such as `use_cases` and `functions`, multiple values are expected
when multiple intents are expressed in the query.

A parser output is not considered correct if it omits an intent that should be
represented and that omission could affect downstream filtering or ranking.

#### Expected Filter Behavior

Each test case should preserve the expected candidate tool IDs for the bound
database snapshot.

The expected candidate list should not be generated at evaluation runtime by
the production filtering implementation.

Instead, it should be generated independently from the database snapshot and
the expected parsed constraints, then reviewed and frozen as benchmark ground
truth.

#### Expected Fallback Behavior

Each relevant test case should record:

- whether fallback should trigger;
- expected retry count;
- expected relaxed fields;
- expected relaxation order;
- expected candidate set after successful fallback where applicable.

#### Expected Ranking Behavior

Ranking validation should preserve expected matching facts rather than only
expected final scores.

The evaluation implementation should independently calculate expected scores
from those matching facts and compare them with production ranking outputs.

Dedicated cases should cover ranking tie-break rules.

#### Recommendation Relevance Ground Truth

V1 should distinguish two forms of relevance:

1. Taxonomy/rule-based relevance
   - Deterministic.
   - Based on category, use case, function, and other structured matches.
   - Useful as a measurable relevance proxy.

2. Semantic relevance
   - Evaluated using an LLM judge.
   - Used because structured taxonomy matching alone cannot fully determine
     whether a recommendation genuinely satisfies the user's natural-language
     need.
   - Treated as a proxy evaluator rather than absolute ground truth.

Future user-behavior data may later provide stronger relevance ground truth.

#### Test Case Categories

The benchmark should include:

- normal queries;
- multi-constraint queries;
- fallback-triggering queries:
  - one relaxation;
  - two relaxations;
  - three relaxations;
- ambiguous queries;
- over-constrained queries;
- edge cases;
- paraphrase/synonym queries;
- spelling-error queries;
- semantically similar queries with small wording differences;
- parser-stability-sensitive queries;
- ranking tie-break cases.


### 2. Pipeline Correctness Evaluation

The V1 correctness evaluation will record results at three levels:

1. Case-level correctness
2. Field/component-level correctness
3. Failure-type distribution

Case-level strict pass/fail will be the primary correctness metric.

Field-level and component-level metrics will be retained to provide diagnostic
detail and to show which lower-level failures contribute to case-level
failures.

Failure types will also be recorded so recurring failure patterns can be
identified.

#### Parser Evaluation

##### Case-Level Pass Condition

A parser case passes only when all required fields correctly represent the
intent expressed in the query after normalization.

A failure in any required field causes the parser case to fail.

##### Field-Level Evaluation

Evaluate independently:

- JSON/schema validity
- category
- must_have.price_type
- must_have.language
- must_have.use_cases
- nice_to_have.use_cases
- functions

For intent-bearing fields such as `use_cases` and `functions`, evaluation
should detect both missing and incorrectly added intents.

##### Parser Failure Types

Examples include:

- schema_error
- missing_field
- incorrect_type
- incorrect_value
- intent_omission
- hallucinated_intent

##### Metrics

Primary:
- Parser Case Accuracy
- Parser Failure Rate

Detailed:
- Field Accuracy by parser field
- Field Failure Rate by parser field
- Failure Type Distribution


#### Filter Evaluation

##### Case-Level Pass Condition

A filter case passes when the actual candidate set exactly matches the expected
candidate set for the benchmark database snapshot.

##### Component-Level Evaluation

Record:

- expected candidate count
- actual candidate count
- correctly retained candidates
- false inclusions
- false exclusions

##### Filter Failure Types

- false_inclusion
- false_exclusion
- incorrect_empty_result
- incorrect_non_empty_result

##### Metrics

Primary:
- Filter Case Accuracy
- Filter Failure Rate

Detailed:
- Candidate Precision
- Candidate Recall
- False Inclusion Rate
- False Exclusion Rate
- Failure Type Distribution


#### Fallback Evaluation

##### Case-Level Pass Condition

A fallback case passes only when all expected fallback behavior is correct:

- trigger decision
- retry count
- relaxed fields
- relaxation order
- resulting candidate set

##### Component-Level Evaluation

Record correctness separately for:

- trigger
- retry count
- each relaxation step
- relaxed field
- relaxation order
- final recovered candidate set

##### Fallback Failure Types

- missing_trigger
- false_trigger
- incorrect_retry_count
- incorrect_relaxed_field
- incorrect_relaxation_order
- incorrect_recovered_candidates

##### Metrics

Primary:
- Fallback Case Accuracy
- Fallback Failure Rate

Detailed:
- Trigger Accuracy
- Retry Count Accuracy
- Relaxation-Step Accuracy
- Relaxation-Order Accuracy
- Recovered-Candidate Accuracy
- Failure Type Distribution


#### Ranking Evaluation

##### Case-Level Pass Condition

A ranking case passes only when:

- all expected candidates are included;
- expected matching facts are correctly reflected;
- scores are correctly calculated;
- candidate ordering is correct;
- tie-break behavior is correct when applicable;
- top-k output is correct.

##### Component-Level Evaluation

Record separately:

- candidate coverage
- matching-fact correctness
- score correctness
- ordering correctness
- tie-break correctness
- top-k correctness

##### Ranking Failure Types

- missing_candidate
- incorrect_matching_fact
- incorrect_score
- incorrect_order
- incorrect_tie_break
- incorrect_top_k

##### Metrics

Primary:
- Ranking Case Accuracy
- Ranking Failure Rate

Detailed:
- Candidate Coverage Accuracy
- Matching-Fact Accuracy
- Score Accuracy
- Ordering Accuracy
- Tie-Break Accuracy
- Top-K Accuracy
- Failure Type Distribution


#### Relationship Between Case-Level and Detailed Metrics

V1 will preserve both case-level and detailed evaluation records.

This allows analysis of questions such as:

- Which parser fields most frequently contribute to case-level failure?
- Are filter failures primarily caused by false exclusions or false inclusions?
- Which fallback steps are most failure-prone?
- Do ranking failures mainly originate from scoring or ordering?

V1 does not need to calculate formal statistical correlations between these
metrics. The detailed records should first provide enough data to observe
relationships between component-level failures and overall case-level
correctness.

### 3. Stability Evaluation

The V1 evaluation will measure stability at both the end-to-end level and the
downstream replay level.

#### A. End-to-End Stability

For each selected stability test case, the same raw query will be executed
multiple times through:

query
→ parser
→ filter
→ fallback
→ ranking
→ final results

This measures the stability of the system as actually experienced from the
user-facing input boundary.

#### B. Downstream Replay Stability

A saved normalized parser output will be replayed multiple times through:

saved parsed output
→ filter
→ fallback
→ ranking
→ final results

This isolates downstream behavior from LLM parser variability.

If end-to-end stability is lower than downstream replay stability, the parser
is a likely source of variability.

#### Parser Stability

For repeated runs of the same query, compare normalized parser outputs.

Record:

- exact normalized-output stability;
- field-level stability for:
  - category;
  - price_type;
  - language;
  - use_cases;
  - functions.

V1 will use normalized structured equality rather than semantic similarity as
the primary parser-stability criterion.

#### Filter Stability

For repeated runs using the same parsed input, compare:

- exact candidate set;
- candidate count.

Because the filter stage is deterministic, expected stability should be 100%
for a fixed database snapshot.

#### Fallback Stability

Compare across repeated runs:

- trigger decision;
- retry count;
- relaxed fields;
- relaxation order;
- recovered candidate set.

For a fixed parsed input and database snapshot, expected stability should be
100%.

#### Ranking Stability

Compare:

- candidate scores;
- sorted order;
- tie-break behavior;
- top-k output.

For fixed candidates, parsed input, and database snapshot, expected stability
should be 100%.

#### Final Recommendation Stability

Record at least two metrics:

1. Exact Top-K Stability
   - Same recommended tools in the same order.

2. Top-K Set Stability
   - Same recommended tools regardless of order.

More advanced ranking-consistency metrics may be added later if needed.

#### Repeated Runs

Each selected stability test case will be executed 10 times.

#### Canonical Reference

The canonical reference for stability comparison will be the benchmark expected
output rather than the first runtime output.

Each repeated run will be compared against the benchmark expectation.

This avoids treating an arbitrary or potentially incorrect first run as the
reference.

#### Stability Metrics

For each stage:

Stability Rate
= number of repeated runs matching the benchmark expectation
  / total repeated runs

The report should include:

- parser exact stability;
- parser field-level stability;
- filter stability;
- fallback stability;
- ranking stability;
- final exact top-k stability;
- final top-k set stability.

## 4. Recommendation Relevance Evaluation

The V1 relevance evaluation will use an LLM judge to evaluate the final
user-visible recommendations against the user's original natural-language
query.

### Judge Input

The judge should receive:

- raw user query;
- recommended tool name;
- tool description;
- category;
- functions;
- use cases;
- language;
- price type.

The normalized `parsed_query` may also be preserved as supporting context for
diagnosis, but the primary relevance judgment should be based on the raw user
query and the recommended tool metadata.

This reduces the risk that an incorrect parser output biases the relevance
evaluation itself.

### Evaluation Unit

The judge evaluates each recommended tool independently.

The primary evaluation unit is therefore:

user query

- one recommended tool
  → relevance score

### Graded Relevance

V1 will use graded relevance rather than a binary relevant / irrelevant label.

Initial scoring scale:

- 0 — Not relevant
- 1 — Weakly relevant
- 2 — Partially relevant
- 3 — Relevant
- 4 — Highly relevant

The rubric for each score should be defined explicitly in the judge prompt.

The judge should consider how well each tool satisfies the need expressed in
the raw user query based on:

- description;
- category;
- functions;
- use cases;
- language;
- price type.

### Judge Execution Strategy

For each evaluation query, the LLM judge will evaluate the user-visible
recommended tools in a single request.

Since the current system returns the top three recommendations to the user,
V1 only needs to judge those final top-three tools.

The judge receives:

- raw user query;
- metadata for each of the top-three recommended tools:

  - tool ID and name;
  - description;
  - category;
  - functions;
  - use cases;
  - language;
  - price type.

Each tool should be evaluated independently against the raw user query using
the same relevance rubric.

The presence or quality of another recommended tool should not increase or
decrease the relevance score assigned to a particular tool.

The LLM judge should return structured tool-level relevance scores only.

Example conceptual output:

```json
{
  "tool_scores": [
    {"tool_id": 12, "relevance": 4},
    {"tool_id": 31, "relevance": 3},
    {"tool_id": 8, "relevance": 2}
  ]
}
```

Aggregate relevance metrics should be calculated deterministically by the
evaluation code rather than by the LLM.

### Relevance Metrics

V1 will use two primary relevance metrics:

1. **Top-1 Relevance**

   - Relevance score of the highest-ranked recommendation.
   - Measures the quality of the recommendation receiving the highest user
     exposure.

2. **Average Top-3 Relevance**

   - Mean relevance score of the three user-visible recommendations.
   - Measures the semantic quality of the recommendation set actually shown
     to the user.

The current V1 does not include:

- Average Top-10 Candidate Relevance;
- threshold-based Relevant Recommendation Rate;
- LLM-judge stability evaluation.

These may be reconsidered later if the system scale or evaluation needs make
them useful.

The current priority is to establish a simple and usable semantic relevance
signal for the recommendations that directly affect the user experience.

## 5. Evaluation Output / Report Schema

The evaluation system should produce two levels of output:

1. Case-level evaluation records
2. Run-level aggregated summaries

### Case-Level Record

Each test case should preserve results from the evaluation dimensions so that
pipeline behavior, stability, and recommendation quality can be analyzed
together.

The record should include:

- case ID;
- raw query;
- benchmark/database version;
- parser correctness and field-level results;
- parser failure types;
- filter correctness and candidate differences;
- fallback behavior;
- ranking correctness;
- stability metrics;
- tool-level LLM relevance scores;
- Top-1 relevance;
- Average Top-3 relevance.

### Run-Level Summary

Each evaluation run should aggregate:

#### Correctness

- parser case accuracy / failure rate;
- parser field-level accuracy;
- filter case accuracy / failure rate;
- fallback case accuracy / failure rate;
- ranking case accuracy / failure rate;
- failure-type distributions.

#### Stability

- parser stability;
- parser field-level stability;
- filter stability;
- fallback stability;
- ranking stability;
- final top-k stability.

#### Relevance

- Average Top-1 Relevance across evaluation cases;
- Average Top-3 Relevance across evaluation cases.

### Version Metadata

Every evaluation run should record:

- evaluation run ID;
- system/code version;
- benchmark version;
- database snapshot/version;
- parser model;
- parser prompt version;
- LLM judge model;
- judge prompt version;
- evaluation timestamp.

This metadata is required so metric changes can be attributed to controlled
system changes rather than unrelated changes in data, prompts, or models.

Recording the judge model and prompt version does not imply that V1 will
evaluate judge stability. They are retained only for reproducibility and
traceability.

### Failed-Case Preservation

Failed cases should be preserved individually rather than only aggregated into
summary metrics.

This allows later inspection of:

- what failed;
- where the failure occurred;
- which fields or components were affected;
- whether the failure also affected recommendation relevance or final output.
