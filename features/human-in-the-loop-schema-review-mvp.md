## Human-in-the-Loop Schema Review MVP - Partly DONE, still need way for user to add annotations

### Overview
Add an optional schema review step where users can select tables and add annotations before exploration begins.

### 1. Add Schema Review State Management
**File:** `app.py`
**Function:** Update `initialize_session_state()`

```python
def initialize_session_state():
    """Initialize session state variables"""
    # ... existing code ...
    
    # NEW: Schema review state
    if 'schema_reviewed' not in st.session_state:
        st.session_state.schema_reviewed = False
    if 'selected_tables' not in st.session_state:
        st.session_state.selected_tables = {}
    if 'table_annotations' not in st.session_state:
        st.session_state.table_annotations = {}
    if 'raw_schema' not in st.session_state:
        st.session_state.raw_schema = None
```

### 2. Add Schema Review Interface
**File:** `app.py`
**Function:** `render_schema_review()` (new function)

```python
def render_schema_review():
    """Render schema review and table selection interface"""
    if not st.session_state.raw_schema:
        st.info("👆 Connect and introspect schema first")
        return False
    
    st.subheader("📋 Schema Review & Table Selection")
    st.markdown("Review discovered tables and select which ones to explore:")
    
    # Quick selection options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Select All"):
            for table_name in st.session_state.raw_schema["tables"].keys():
                st.session_state.selected_tables[table_name] = True
            st.rerun()
    
    with col2:
        if st.button("❌ Deselect All"):
            for table_name in st.session_state.raw_schema["tables"].keys():
                st.session_state.selected_tables[table_name] = False
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset to Default"):
            st.session_state.selected_tables = {}
            st.session_state.table_annotations = {}
            st.rerun()
    
    st.divider()
    
    # Table selection interface
    tables = st.session_state.raw_schema["tables"]
    
    for table_name, table_info in tables.items():
        # Initialize selection state (default to True)
        if table_name not in st.session_state.selected_tables:
            st.session_state.selected_tables[table_name] = True
        
        # Initialize annotation state
        if table_name not in st.session_state.table_annotations:
            st.session_state.table_annotations[table_name] = ""
        
        with st.expander(f"📊 {table_name} ({table_info['type']}) - {len(table_info['columns'])} columns"):
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Table selection checkbox
                selected = st.checkbox(
                    "Include in exploration",
                    value=st.session_state.selected_tables[table_name],
                    key=f"select_{table_name}"
                )
                st.session_state.selected_tables[table_name] = selected
            
            with col2:
                # Table annotation
                annotation = st.text_area(
                    "Table description/notes (optional)",
                    value=st.session_state.table_annotations[table_name],
                    placeholder="e.g., 'Primary customer data table' or 'Contains PII - be careful'",
                    key=f"annotate_{table_name}",
                    height=60
                )
                st.session_state.table_annotations[table_name] = annotation
            
            # Show column preview
            if selected:
                st.write("**Columns:**")
                columns_df = pd.DataFrame(table_info["columns"])
                st.dataframe(columns_df, use_container_width=True, height=150)
    
    # Validation and proceed button
    selected_count = sum(st.session_state.selected_tables.values())
    
    st.divider()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if selected_count == 0:
            st.error("⚠️ Please select at least one table to explore")
        else:
            st.success(f"✅ {selected_count} table(s) selected for exploration")
    
    with col2:
        if st.button(
            "🚀 Proceed with Selected Tables",
            disabled=selected_count == 0,
            type="primary"
        ):
            st.session_state.schema_reviewed = True
            return True
    
    return False
```

### 3. Modify Schema Introspection
**File:** `app.py`
**Method:** `introspect_schema()` in StreamlitDataTwin class

```python
def introspect_schema(self, conn):
    """Introspect database schema with artifact capture"""
    # ... existing introspection code ...
    
    # Store RAW schema (before filtering)
    self.raw_schema = schema
    
    # Store complete schema in artifacts
    self.artifacts["schema"] = {
        "timestamp": datetime.now().isoformat(),
        "table_count": len(schema["tables"]),
        "schema_data": schema
    }
    
    self.schema = schema
    return schema

# NEW: Add method to apply table selections
def apply_table_selections(self, selected_tables: Dict[str, bool], annotations: Dict[str, str]):
    """Filter schema based on user selections and add annotations"""
    if not self.raw_schema:
        return
    
    # Create filtered schema
    filtered_schema = {"tables": {}, "relationships": []}
    
    for table_name, table_info in self.raw_schema["tables"].items():
        if selected_tables.get(table_name, False):
            # Add table with annotation
            table_copy = copy.deepcopy(table_info)
            if annotations.get(table_name):
                table_copy["user_annotation"] = annotations[table_name]
            
            filtered_schema["tables"][table_name] = table_copy
    
    # Update working schema
    self.schema = filtered_schema
    
    # Store selection info in artifacts
    self.artifacts["table_selections"] = {
        "timestamp": datetime.now().isoformat(),
        "selected_tables": selected_tables,
        "annotations": annotations,
        "total_tables": len(self.raw_schema["tables"]),
        "selected_count": sum(selected_tables.values())
    }
```

### 4. Update Main Interface Workflow
**File:** `app3.py`
**Function:** `render_main_interface()` modification

```python
def render_main_interface(connection_info, missing_vars, max_queries):
    """Render main application interface"""
    st.title("🔍 DataTwin: Autonomous Data Explorer")
    st.markdown("*Intelligent database exploration with hierarchical insights*")
    
    if missing_vars:
        st.error("Please configure your Snowflake connection in the sidebar first.")
        return
    
    # NEW: Multi-step workflow
    if not st.session_state.raw_schema:
        # Step 1: Schema Introspection
        if st.button("🔍 Connect & Discover Schema", type="primary"):
            with st.spinner("🔄 Connecting and discovering schema..."):
                try:
                    datatwin = StreamlitDataTwin(
                        llm_provider=st.session_state.llm_provider,
                        max_queries=max_queries
                    )
                    
                    conn_params = {
                        'account': connection_info['SNOWFLAKE_ACCOUNT'],
                        'user': connection_info['SNOWFLAKE_USERNAME'],
                        'password': os.getenv('SNOWFLAKE_PASSWORD', ''),
                        'database': connection_info['SNOWFLAKE_DATABASE'],
                        'warehouse': connection_info['SNOWFLAKE_WAREHOUSE'],
                        'schema': connection_info['SNOWFLAKE_SCHEMA']
                    }
                    
                    conn = datatwin.connect_snowflake(conn_params)
                    schema = datatwin.introspect_schema(conn)
                    conn.close()
                    
                    # Store in session state for review
                    st.session_state.raw_schema = schema
                    st.session_state.datatwin = datatwin
                    
                    st.success("✅ Schema discovered! Review tables below.")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Schema discovery failed: {str(e)}")
    
    elif not st.session_state.schema_reviewed:
        # Step 2: Schema Review
        if render_schema_review():
            st.rerun()
    
    else:
        # Step 3: Run Exploration
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button(
                "🚀 Start Autonomous Exploration", 
                disabled=st.session_state.exploration_running,
                type="primary"
            ):
                st.session_state.exploration_running = True
                
                with st.spinner("🔄 Exploring selected tables..."):
                    try:
                        datatwin = st.session_state.datatwin
                        
                        # NEW: Apply table selections before exploration
                        datatwin.apply_table_selections(
                            st.session_state.selected_tables,
                            st.session_state.table_annotations
                        )
                        
                        # Reconnect and run exploration
                        conn_params = {...}  # Same as above
                        conn = datatwin.connect_snowflake(conn_params)
                        results = datatwin.run_exploration(conn)
                        conn.close()
                        
                        st.session_state.exploration_results = results
                        st.success("✅ Exploration completed!")
                        
                    except Exception as e:
                        st.error(f"❌ Exploration failed: {str(e)}")
                    finally:
                        st.session_state.exploration_running = False
        
        with col2:
            # Show selection summary
            selected_count = sum(st.session_state.selected_tables.values())
            st.metric("Tables Selected", selected_count)
            
            # Option to go back and modify selection
            if st.button("📝 Modify Table Selection"):
                st.session_state.schema_reviewed = False
                st.rerun()
```

### 5. Update Prompt Generation
**File:** `app.py`
**Method:** `generate_llm_prompt()` modification

```python
def generate_llm_prompt(self) -> str:
    """Generate exploration prompt with table annotations"""
    # ... existing code ...
    
    # NEW: Include table annotations in schema context
    enhanced_schema = copy.deepcopy(self.schema)
    
    # Add user annotations to prompt context
    annotation_context = ""
    for table_name, table_info in enhanced_schema["tables"].items():
        if "user_annotation" in table_info:
            annotation_context += f"\n- {table_name}: {table_info['user_annotation']}"
    
    if annotation_context:
        enhanced_schema["user_context"] = f"User provided context:{annotation_context}"
    
    prompt = f"""You are an expert data analyst exploring a database to understand its structure, content, and blind spots.

You have run {self.query_count} queries so far, and can run up to {self.max_queries} total queries.

DATABASE SCHEMA:
{json.dumps(enhanced_schema, indent=2)}

{annotation_context}

EXPLORATION HISTORY:
{history_context}"""
    
    # Rest same as before
```

### Implementation Order
1. **Step 1**: Add session state management for schema review
2. **Step 2**: Create `render_schema_review()` interface function
3. **Step 3**: Modify `introspect_schema()` to store raw schema
4. **Step 4**: Add `apply_table_selections()` method
5. **Step 5**: Update main interface workflow to be multi-step
6. **Step 6**: Enhance prompt generation with annotations
7. **Step 7**: Test complete workflow end-to-end

### Testing Strategy
- Test with database having 10+ tables to verify selection works
- Verify annotations appear in generated prompts
- Test edge cases (select no tables, all tables, etc.)
- Confirm exploration quality improves with focused table selection