## Feature: Quick Scale Assessment Implementation Spec

### Overview
Add a fast data scale assessment step that runs before autonomous exploration to inform the LLM about dataset size and adjust query strategy accordingly.

### Problem Statement
Currently, the LLM generates queries without knowing whether it's dealing with thousands or billions of rows, leading to:
- Potential query timeouts on large datasets
- Inefficient complex queries on massive tables
- No strategic adjustment based on data volume

### Solution
Implement a quick row count assessment that:
1. Runs fast `COUNT(*)` queries on all selected tables
2. Categorizes data scale (small/medium/large)
3. Provides strategy guidance to the LLM
4. Shows scale information in the UI

## Implementation Plan

### Phase 1: Core Scale Assessment Method

Add to `StreamlitDataTwin` class:

```python
def assess_data_scale(self, conn) -> Dict:
    """Quick assessment of table sizes to inform query strategy"""
    cursor = conn.cursor()
    scale_info = {}
    
    try:
        # Build a UNION query to get row counts for all selected tables
        table_names = list(self.schema["tables"].keys())
        count_queries = []
        
        for table_name in table_names:
            count_queries.append(f"SELECT '{table_name}' as table_name, COUNT(*) as row_count FROM {table_name}")
        
        union_query = " UNION ALL ".join(count_queries)
        
        st.write("📊 Assessing data scale across tables...")
        cursor.execute(union_query)
        results = cursor.fetchall()
        
        total_rows = 0
        for table_name, row_count in results:
            scale_info[table_name] = row_count
            total_rows += row_count
            st.write(f"  • {table_name}: {row_count:,} rows")
        
        # Categorize scale
        if total_rows < 100_000:
            scale_category = "small"
            query_strategy = "Can use complex joins and detailed analysis"
        elif total_rows < 10_000_000:
            scale_category = "medium" 
            query_strategy = "Use sampling and limit result sets"
        else:
            scale_category = "large"
            query_strategy = "Focus on aggregates, avoid large result sets, use LIMIT extensively"
        
        scale_summary = {
            "total_rows": total_rows,
            "table_counts": scale_info,
            "scale_category": scale_category,
            "query_strategy": query_strategy,
            "largest_table": max(scale_info.keys(), key=lambda k: scale_info[k]),
            "smallest_table": min(scale_info.keys(), key=lambda k: scale_info[k])
        }
        
        # Store in artifacts
        self.artifacts["data_scale"] = {
            "timestamp": datetime.now().isoformat(),
            "scale_summary": scale_summary
        }
        
        st.success(f"✅ Data scale: {scale_category} ({total_rows:,} total rows)")
        return scale_summary
        
    finally:
        cursor.close()
```

### Phase 2: Enhanced LLM Prompt Generation

Modify `generate_llm_prompt` method to include scale context:

```python
def generate_llm_prompt(self) -> str:
    """Generate exploration prompt with hierarchical context and scale awareness"""
    prompt = f"""You are an expert data analyst exploring a database to understand its structure, content, and blind spots.

You have run {len(self.query_history)} queries so far, and can run up to {self.max_queries} total queries.

DATABASE SCHEMA:
{json.dumps(self.schema, indent=2)}"""

    # Add scale information if available
    if "data_scale" in self.artifacts:
        scale_info = self.artifacts["data_scale"]["scale_summary"]
        prompt += f"""

DATA SCALE ASSESSMENT:
- Total rows across all tables: {scale_info['total_rows']:,}
- Scale category: {scale_info['scale_category']}
- Query strategy: {scale_info['query_strategy']}
- Largest table: {scale_info['largest_table']} ({scale_info['table_counts'][scale_info['largest_table']]:,} rows)
- Smallest table: {scale_info['smallest_table']} ({scale_info['table_counts'][scale_info['smallest_table']]:,} rows)

IMPORTANT: Adjust your queries based on the data scale. For large datasets, use LIMIT clauses, focus on aggregates, and avoid complex joins that might timeout."""

    # ... rest of prompt generation
```

### Phase 3: Integration with Exploration Flow

Update `run_exploration` method:

```python
def run_exploration(self, conn) -> str:
    """Main exploration loop with scale assessment and hierarchical summarization"""
    results = []
    
    # First, assess data scale before starting queries
    try:
        scale_summary = self.assess_data_scale(conn)
        results.append(f"📊 Data scale assessed: {scale_summary['scale_category']} ({scale_summary['total_rows']:,} total rows)")
        
        # Add scale info to session state for UI display
        if hasattr(st, 'session_state'):
            st.session_state.data_scale = scale_summary
            
    except Exception as e:
        results.append(f"⚠️ Could not assess data scale: {str(e)}")
    
    # Continue with existing exploration loop...
```

### Phase 4: UI Enhancements

#### A. Table Selection Interface
Show row counts in table selection:

```python
# Show table details for selected tables
if selected_tables:
    with st.expander(f"📋 Preview Selected Tables ({len(selected_tables)})"):
        for table_name in selected_tables[:5]:
            table_info = schema["tables"][table_name]
            # Add row count if available
            row_count_text = ""
            if hasattr(st.session_state, 'data_scale') and table_name in st.session_state.data_scale['table_counts']:
                row_count = st.session_state.data_scale['table_counts'][table_name]
                row_count_text = f" - {row_count:,} rows"
            
            st.write(f"**{table_name}** ({table_info['type']}) - {len(table_info['columns'])} columns{row_count_text}")
```

#### B. Scale Visualization
Add scale indicator to sidebar:

```python
# Show data scale in sidebar
if st.session_state.datatwin and hasattr(st.session_state, 'data_scale'):
    scale_info = st.session_state.data_scale
    scale_color = {"small": "🟢", "medium": "🟡", "large": "🔴"}[scale_info['scale_category']]
    st.info(f"{scale_color} Data Scale: {scale_info['scale_category'].title()} ({scale_info['total_rows']:,} rows)")
```

#### C. Results Tab Enhancement
Add scale summary to results:

```python
with tab4:  # Schema tab
    st.subheader("🏗️ Database Schema")
    
    # Show scale assessment if available
    if hasattr(st.session_state, 'data_scale'):
        scale_info = st.session_state.data_scale
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rows", f"{scale_info['total_rows']:,}")
        with col2:
            st.metric("Scale Category", scale_info['scale_category'].title())
        with col3:
            st.metric("Largest Table", scale_info['largest_table'])
    
    # Existing schema display...
```

## Alternative Approaches

### Option 1: Metadata-Based Assessment (Faster)
Use Snowflake's `INFORMATION_SCHEMA.TABLES` for instant results:

```sql
SELECT table_name, row_count 
FROM INFORMATION_SCHEMA.TABLES 
WHERE table_schema = CURRENT_SCHEMA()
```

**Pros:** Instant execution
**Cons:** May not be accurate if statistics are stale

### Option 2: Sampling-Based Assessment
Use `TABLESAMPLE` for large tables:

```sql
SELECT 'TABLE_NAME' as table_name, 
       COUNT(*) * 100 as estimated_rows 
FROM TABLE_NAME TABLESAMPLE (1)
```

**Pros:** Fast for very large tables
**Cons:** Less accurate, more complex logic

## Technical Considerations

### Performance
- `COUNT(*)` queries are typically well-optimized by database engines
- UNION ALL approach minimizes round trips
- Consider timeout handling for extremely large tables

### Error Handling
- Graceful degradation if scale assessment fails
- Continue exploration even without scale information
- Log scale assessment errors for debugging

### Session State Management
- Store scale info in session state for UI persistence
- Include scale data in artifacts for historical analysis
- Handle session state cleanup on provider changes

## Testing Strategy

### Unit Tests
- Test scale categorization logic with various row counts
- Test prompt generation with and without scale data
- Test error handling for failed scale assessments

### Integration Tests
- Test with small sample datasets (< 1K rows)
- Test with medium datasets (10K-1M rows)
- Test timeout behavior simulation

### User Acceptance Tests
- Verify UI shows scale information correctly
- Confirm LLM generates appropriate queries for each scale
- Validate exploration performance improvements

## Success Metrics

### Performance Improvements
- Reduced query timeouts on large datasets
- Faster average exploration time
- More successful query completion rates

### Query Quality
- More appropriate LIMIT clauses in generated queries
- Better aggregation strategies for large tables
- Improved sampling techniques

### User Experience
- Clear visibility into dataset scale
- Informed table selection decisions
- Reduced frustration with timeouts

## Future Enhancements

### Smart Query Optimization
- Dynamic LIMIT values based on table size
- Intelligent sampling strategies
- Partition-aware queries for very large tables

### Advanced Scale Metrics
- Data freshness assessment
- Column cardinality analysis
- Index and constraint detection

### Visual Scale Indicators
- Table size heat maps
- Interactive scale filters
- Performance prediction tooltips

## Implementation Priority
**Priority: Medium-High**
**Effort: Small-Medium (2-3 hours)**
**Impact: High (significant UX and performance improvement)**

This feature provides substantial value for minimal implementation effort and should be prioritized in the next development cycle.