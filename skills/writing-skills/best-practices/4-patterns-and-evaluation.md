# Skill authoring best practices, part 4 of 6: patterns and evaluation

## Common patterns

### Template pattern

Provide templates for output format. Match the level of strictness to your needs.

**For strict requirements** (like API responses or data formats):

````markdown  theme={null}
## Report structure

ALWAYS use this exact template structure:

```markdown
# [Analysis Title]

## Executive summary
[One-paragraph overview of key findings]

## Key findings
- Finding 1 with supporting data
- Finding 2 with supporting data
- Finding 3 with supporting data

## Recommendations
1. Specific actionable recommendation
2. Specific actionable recommendation
```
````

**For flexible guidance** (when adaptation is useful):

````markdown  theme={null}
## Report structure

Here is a sensible default format, but use your best judgment based on the analysis:

```markdown
# [Analysis Title]

## Executive summary
[Overview]

## Key findings
[Adapt sections based on what you discover]

## Recommendations
[Tailor to the specific context]
```

Adjust sections as needed for the specific analysis type.
````

### Examples pattern

For Skills where output quality depends on seeing examples, provide input/output pairs just like in regular prompting:

````markdown  theme={null}
## Commit message format

Generate commit messages following these examples:

**Example 1:**
Input: Added user authentication with JWT tokens
Output:
```
feat(auth): implement JWT-based authentication

Add login endpoint and token validation middleware
```

**Example 2:**
Input: Fixed bug where dates displayed incorrectly in reports
Output:
```
fix(reports): correct date formatting in timezone conversion

Use UTC timestamps consistently across report generation
```

**Example 3:**
Input: Updated dependencies and refactored error handling
Output:
```
chore: update dependencies and refactor error handling

- Upgrade lodash to 4.17.21
- Standardize error response format across endpoints
```

Follow this style: type(scope): brief description, then detailed explanation.
````

Examples help agents understand the desired style and level of detail more clearly than descriptions alone.

### Conditional workflow pattern

Guide agents through decision points:

```markdown  theme={null}
## Document modification workflow

1. Determine the modification type:

   **Creating new content?** → Follow "Creation workflow" below
   **Editing existing content?** → Follow "Editing workflow" below

2. Creation workflow:
   - Use docx-js library
   - Build document from scratch
   - Export to .docx format

3. Editing workflow:
   - Unpack existing document
   - Modify XML directly
   - Validate after each change
   - Repack when complete
```

<Tip>
  If workflows become large or complicated with many steps, consider pushing them into separate files and tell the agent to read the appropriate file based on the task at hand.
</Tip>

## Evaluation and iteration

### Build evaluations first

**Create evaluations BEFORE writing extensive documentation.** This ensures your Skill solves real problems rather than documenting imagined ones.

**Evaluation-driven development:**

1. **Identify gaps**: Run your agent on representative tasks without a Skill. Document specific failures or missing context
2. **Create evaluations**: Build three scenarios that test these gaps
3. **Establish baseline**: Measure the agent's performance without the Skill
4. **Write minimal instructions**: Create just enough content to address the gaps and pass evaluations
5. **Iterate**: Execute evaluations, compare against baseline, and refine

This approach ensures you're solving actual problems rather than anticipating requirements that may never materialize.

**Evaluation structure**:

```json  theme={null}
{
  "skills": ["pdf-processing"],
  "query": "Extract all text from this PDF file and save it to output.txt",
  "files": ["test-files/document.pdf"],
  "expected_behavior": [
    "Successfully reads the PDF file using an appropriate PDF processing library or command-line tool",
    "Extracts text content from all pages in the document without missing any pages",
    "Saves the extracted text to a file named output.txt in a clear, readable format"
  ]
}
```

<Note>
  This example demonstrates a data-driven evaluation with a simple testing rubric. We do not currently provide a built-in way to run these evaluations. Users can create their own evaluation system. Evaluations are your source of truth for measuring Skill effectiveness.
</Note>

### Develop Skills iteratively in the main session

The main session designs, tests, and refines the Skill. It may observe a
real task in the same session or use an already-authorized implementation
worker for implementation behavior. Do not create a separate evaluator,
reviewer, or analyst worker for this cycle.

**Creating a new Skill:**

1. **Complete a task without a Skill**: Work through a problem in the main session using normal prompting. Notice what information you repeatedly provide.

2. **Identify the reusable pattern**: After completing the task, identify what context you provided that would be useful for similar future tasks.

   **Example**: If you worked through a BigQuery analysis, you might have provided table names, field definitions, filtering rules (like "always exclude test accounts"), and common query patterns.

3. **Create the Skill in the main session**: capture the reusable pattern, schemas, naming conventions, and filtering rules.

   <Tip>
     Modern agents understand the Skill format and structure natively. You don't need special system prompts or a "writing skills" skill to get help creating Skills. Simply ask the agent to create a Skill and it will generate properly structured SKILL.md content with appropriate frontmatter and body content.
   </Tip>

4. **Review for conciseness**: Remove explanations the runtime already supplies and keep the actionable rule.

5. **Improve information architecture**: Organize the content so heavy references are separate and directly linked.

6. **Test on similar tasks**: Run related cases in the main session or, when implementation behavior requires it, through the authorized implementer worker. Observe whether the Skill is found and applied.

7. **Iterate based on observation**: If a case struggles or misses something, record the exact evidence and update the smallest responsible section.

**Iterating on existing Skills:**

The same evidence cycle continues when improving Skills:

* **Designing and reviewing in the main session**
* **Testing the Skill in the main session or an authorized implementation turn**
* **Recording observed behavior** and applying the smallest evidence-backed correction

1. **Use the Skill in real workflows**: Run actual tasks in the main session, not only hypothetical summaries.

2. **Observe behavior**: Note where the current session or authorized worker struggles, succeeds, or makes unexpected choices.

   **Example observation**: "The task wrote the query but forgot to filter out test accounts, even though the Skill mentions this rule."

3. **Improve in the main session**: Record the current SKILL.md and the evidence, then adjust the wording or structure that allowed the miss.

4. **Review the change**: Make the rule prominent and operational without duplicating the workflow or adding unsupported claims.

5. **Apply and test changes**: Update the Skill and rerun the same evidence-backed scenarios.

6. **Repeat based on usage**: Continue the observe-refine-test cycle as new evidence appears.

**Gathering team feedback:**

1. Share Skills with teammates and observe their usage
2. Ask: Does the Skill activate when expected? Are instructions clear? What's missing?
3. Incorporate feedback to address blind spots in your own usage patterns

**Why this approach works**: The main session has the requirements and evidence in
one place, so it can refine Skills from observed behavior without paying for a
separate evaluator context.

### Observe how agents navigate Skills

As you iterate on Skills, pay attention to how agents actually use them in practice. Watch for:

* **Unexpected exploration paths**: Does the agent read files in an order you didn't anticipate? This might indicate your structure isn't as intuitive as you thought
* **Missed connections**: Does the agent fail to follow references to important files? Your links might need to be more explicit or prominent
* **Overreliance on certain sections**: If the agent repeatedly reads the same file, consider whether that content should be in the main SKILL.md instead
* **Ignored content**: If the agent never accesses a bundled file, it might be unnecessary or poorly signaled in the main instructions

Iterate based on these observations rather than assumptions. The 'name' and 'description' in your Skill's metadata are particularly critical. Agents use these when deciding whether to trigger the Skill in response to the current task. Make sure they clearly describe what the Skill does and when it should be used.
