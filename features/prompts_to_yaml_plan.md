## Feature: Externalize Prompts to YAML Configuration

### Overview
Extract all LLM prompts from the Python code into a `prompts.yaml` file for easier editing, versioning, and iteration.

### 1. Create Prompts Configuration File
**File:** `prompts.yaml` (new file)
**Location:** Same directory as `app3.py`

```yaml
exploration:
  main_prompt: |
    You are an expert data analyst exploring a database to understand its structure, content, and blind spots.
    
    You have run {query_count} queries so far, and can run up to {max_queries} total queries.
    
    DATABASE SCHEMA:
    {schema}
    
    EXPLORATION HISTORY:
    {history_context}
    
    Based on the schema and previous exploration, generate:
    1. The next SQL query to run (must be valid Snowflake SQL)
    2. Brief explanation of what you're trying to learn
    
    Focus on:
    - Understanding data distribution and patterns
    - Finding relationships between tables  
    - Identifying data quality issues
    - Discovering business insights
    
    Return ONLY:
    SQL: [your query]
    REASONING: [why you chose this query]
    
    Keep SQL concise and efficient.

analysis:
  thinking_prompt: |
    Analyze these SQL results for insights:
    
    SQL Query: {sql}
    {summary}
    
    {sample_info}
    
    Provide analysis in this format:
    1. What we learned: Key insights from this query
    2. Implications: What these results tell us about the data
    3. Next directions: What to explore next
    
    Keep it concise.

summarization:
  hierarchical_summary: |
    Based on queries {start_query} through {end_query}, create a structured summary:
    
    ## TABLE INSIGHTS
    For each table explored:
    - Data coverage patterns (sparse/dense areas)
    - Key relationships discovered
    - Data quality observations
    
    ## RELATIONSHIP PATTERNS
    - Foreign key patterns found
    - Cross-table connections
    - Data flow insights
    
    ## DATA QUALITY FINDINGS
    - Missing data patterns
    - Anomalies or inconsistencies
    - Completeness observations
    
    ## KEY DISCOVERIES
    - Most important insights from this batch
    - Patterns that emerged across queries
    - Questions raised for future exploration
    
    Previous queries in this batch:
    {query_batch}
    
    Format as structured text with clear headers, not bullet points. Be concise but comprehensive.

reporting:
  final_report: |
    Generate a summary report of database exploration.
    
    SCHEMA SUMMARY:
    - Tables: {table_count}
    - Total queries run: {query_count}
    - Summaries generated: {summary_count}
    
    {summaries_context}
    
    KEY FINDINGS:
    {findings}
    
    Generate a markdown report with these sections:
    1. Data Structure Overview
    2. Key Discoveries  
    3. Data Quality Insights
    4. Recommendations
    
    Make it concise but actionable.
```

### 2. Add YAML Loading Function
**File:** `app3.py`
**Function:** Add after imports, before classes

```python
import yaml

def load_prompts(prompts_file: str = "prompts.yaml") -> Dict[str, Any]:
    """Load prompts from YAML configuration file"""
    try:
        with open(prompts_file, 'r', encoding='utf-8') as file:
            prompts = yaml.safe_load(file)
        return prompts
    except FileNotFoundError:
        st.error(f"Prompts file '{prompts_file}' not found. Using default prompts.")
        return get_default_prompts()
    except yaml.YAMLError as e:
        st.error(f"Error parsing prompts file: {e}")
        return get_default_prompts()

def get_default_prompts() -> Dict[str, Any]:
    """Fallback prompts if YAML file is missing"""
    return {
        "exploration": {"main_prompt": "You are a data analyst..."},  # Simplified fallback
        "analysis": {"thinking_prompt": "Analyze these results..."},
        "summarization": {"hierarchical_summary": "Create a summary..."},
        "reporting": {"final_report": "Generate a report..."}
    }
```

### 3. Modify StreamlitDataTwin Class
**File:** `app3.py`
**Changes:** Add prompts to constructor and update methods

```python
class StreamlitDataTwin:
    def __init__(self, llm_provider: str = "anthropic", max_queries: int = 7):
        # ... existing code ...
        
        # NEW: Load prompts configuration
        self.prompts = load_prompts()
    
    def generate_llm_prompt(self) -> str:
        """Generate exploration prompt using template"""
        # Build context components
        history_context = self._build_history_context()
        
        # NEW: Use template from YAML
        prompt_template = self.prompts["exploration"]["main_prompt"]
        prompt = prompt_template.format(
            query_count=self.query_count,
            max_queries=self.max_queries,
            schema=json.dumps(self.schema, indent=2),
            history_context=history_context
        )
        
        # Store prompt in artifacts (same as before)
        self.artifacts["prompts"].append({...})
        return prompt
    
    def analyze_results(self, df: pd.DataFrame, sql: str) -> str:
        """Analyze query results using template"""
        # Build context (same as before)
        summary = f"Returned {len(df)} rows, {len(df.columns)} columns"
        sample_info = "..." # Same logic as before
        
        # NEW: Use template from YAML
        thinking_template = self.prompts["analysis"]["thinking_prompt"]
        thinking_prompt = thinking_template.format(
            sql=sql,
            summary=summary,
            sample_info=sample_info
        )
        
        # Rest same as before
        thinking = self.llm_client.generate(thinking_prompt)
        return thinking
```

### 4. Update Other Prompt Methods
**File:** `app3.py`
**Methods:** `generate_hierarchical_summary()` and `generate_final_report()`

```python
def generate_hierarchical_summary(self, batch_queries: List[Dict]) -> str:
    """Generate structured summary using template"""
    if not batch_queries:
        return ""
    
    # NEW: Use template from YAML
    summary_template = self.prompts["summarization"]["hierarchical_summary"]
    summary_prompt = summary_template.format(
        start_query=batch_queries[0]['query_num'],
        end_query=batch_queries[-1]['query_num'],
        query_batch=json.dumps([f"Q{q['query_num']}: {q['sql'][:100]}... -> {q['result_summary']}" for q in batch_queries], indent=2)
    )
    
    # Rest same as before
    
def generate_final_report(self) -> str:
    """Generate final report using template"""
    # Build context components (same as before)
    
    # NEW: Use template from YAML
    report_template = self.prompts["reporting"]["final_report"]
    report_prompt = report_template.format(
        table_count=len(self.schema.get('tables', {})),
        query_count=len(self.query_history),
        summary_count=len(self.artifacts['hierarchical_summaries']),
        summaries_context=summaries_context,
        findings=json.dumps(self.findings[:15], indent=2)
    )
    
    # Rest same as before
```

### 5. Add Dependencies
**File:** `requirements.txt` (or install manually)
```
pyyaml>=6.0
```

### Implementation Order
1. **Step 1**: Create `prompts.yaml` file with all current prompts
2. **Step 2**: Add YAML loading functions
3. **Step 3**: Modify constructor to load prompts
4. **Step 4**: Update `generate_llm_prompt()` method
5. **Step 5**: Update `analyze_results()` method
6. **Step 6**: Update summarization and reporting methods
7. **Step 7**: Test with existing functionality