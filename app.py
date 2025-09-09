import streamlit as st
import snowflake.connector
import pandas as pd
import json
import os
from datetime import datetime
import copy
from typing import Dict, List, Any, Optional
import anthropic
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

def convert_decimals(obj):
    """Convert Decimal, date, and datetime objects for JSON serialization"""
    import datetime
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(v) for v in obj]
    elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Decimal':
        return float(obj)
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    elif isinstance(obj, datetime.time):
        return obj.isoformat()
    return obj

class LLMClient:
    """Unified LLM client supporting multiple providers"""
    
    def __init__(self, provider: str = "anthropic"):
        self.provider = provider.lower()
        
        if self.provider == "anthropic":
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is required")
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = "claude-sonnet-4-20250514"
        
        elif self.provider == "openai":
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            self.client = OpenAI(api_key=api_key)
            self.model = "gpt-4o"
        
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def generate(self, prompt: str, max_tokens: int = 4000) -> str:
        """Generate response using the configured provider"""
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
                
        except Exception as e:
            return f"Error generating response: {str(e)}"

class StreamlitDataTwin:
    """Enhanced DataTwin with hierarchical summarization"""
    
    def __init__(self, llm_provider: str = "anthropic", max_queries: int = 7):
        self.llm_client = LLMClient(llm_provider)
        self.max_queries = max_queries
        self.query_count = 0
        self.schema = {}
        self.query_history = []
        self.findings = []
        
        # Enhanced artifacts structure with summarization support
        self.artifacts = {
            "session_metadata": {
                "start_time": datetime.now().isoformat(),
                "llm_provider": llm_provider,
                "max_queries": max_queries
            },
            "schema": {},
            "query_history": [],
            "findings_history": [],
            "thinking_prompts": [],
            "thinking_responses": [],
            "prompts": [],
            "hierarchical_summaries": [],
            "summary_trigger_points": [],
            "final_report": {},
            "errors": []
        }
        
        # Track current batch for summarization
        self.current_batch_start = 1
    
    def connect_snowflake(self, connection_params: Dict[str, str]):
        """Connect to Snowflake with error handling"""
        try:
            conn = snowflake.connector.connect(**connection_params)
            return conn
        except Exception as e:
            error_info = {
                "timestamp": datetime.now().isoformat(),
                "error_type": "CONNECTION_ERROR",
                "error_message": str(e),
                "connection_params": {k: v for k, v in connection_params.items() if k != 'password'}
            }
            self.artifacts["errors"].append(error_info)
            raise e
    
    def introspect_schema(self, conn):
        """Introspect database schema with artifact capture and enhanced debugging"""
        cursor = conn.cursor()
        try:
            # First, let's see what's available to us
            st.write("🔍 Checking current session context...")
            
            # Check current database and schema
            cursor.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()")
            current_context = cursor.fetchone()
            st.info(f"Current context - Database: {current_context[0]}, Schema: {current_context[1]}, Warehouse: {current_context[2]}")
            
            # Get available databases
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            available_dbs = [db[1] for db in databases]
            st.write(f"📊 Available databases: {available_dbs}")
            
            # Get connection parameters from environment
            database = os.getenv('SNOWFLAKE_DATABASE')
            schema = os.getenv('SNOWFLAKE_SCHEMA')
            
            st.write(f"🎯 Attempting to use database: {database}, schema: {schema}")
            
            # Try to set the database context
            try:
                cursor.execute(f"USE DATABASE {database}")
                st.success(f"✅ Successfully set database to {database}")
            except Exception as e:
                error_msg = f"Failed to set database {database}: {e}"
                st.error(error_msg)
                st.write(f"Available databases: {available_dbs}")
                
                # Store error in artifacts
                error_info = {
                    "timestamp": datetime.now().isoformat(),
                    "error_type": "DATABASE_ACCESS_ERROR",
                    "error_message": str(e),
                    "requested_database": database,
                    "available_databases": available_dbs
                }
                self.artifacts["errors"].append(error_info)
                raise Exception(error_msg)
            
            # Check available schemas in this database
            cursor.execute("SHOW SCHEMAS")
            schemas = cursor.fetchall()
            available_schemas = [sch[1] for sch in schemas]
            st.write(f"📋 Available schemas in {database}: {available_schemas}")
            
            # Try to set the schema
            try:
                cursor.execute(f"USE SCHEMA {schema}")
                st.success(f"✅ Successfully set schema to {schema}")
            except Exception as e:
                error_msg = f"Failed to set schema {schema}: {e}"
                st.error(error_msg)
                
                # Store error in artifacts
                error_info = {
                    "timestamp": datetime.now().isoformat(),
                    "error_type": "SCHEMA_ACCESS_ERROR",
                    "error_message": str(e),
                    "requested_schema": schema,
                    "available_schemas": available_schemas
                }
                self.artifacts["errors"].append(error_info)
                raise Exception(error_msg)
            
            # Now try to get tables - using a more basic approach
            try:
                # Try the simpler SHOW TABLES approach first
                cursor.execute("SHOW TABLES")
                tables_result = cursor.fetchall()
                st.success(f"📊 Found {len(tables_result)} tables using SHOW TABLES")
                
                # Convert SHOW TABLES result to our expected format
                tables = [(row[1], 'BASE TABLE') for row in tables_result]  # Table name is usually in column 1
                
            except Exception as e:
                st.warning(f"SHOW TABLES failed: {e}")
                # Fallback to INFORMATION_SCHEMA if available
                try:
                    cursor.execute("""
                        SELECT table_name, table_type
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE table_schema = CURRENT_SCHEMA()
                        AND table_type IN ('BASE TABLE', 'VIEW')
                    """)
                    tables = cursor.fetchall()
                    st.success(f"📊 Found {len(tables)} tables using INFORMATION_SCHEMA")
                except Exception as e2:
                    error_msg = f"Both SHOW TABLES and INFORMATION_SCHEMA queries failed: {e2}"
                    st.error(error_msg)
                    
                    # Store error in artifacts
                    error_info = {
                        "timestamp": datetime.now().isoformat(),
                        "error_type": "TABLE_DISCOVERY_ERROR",
                        "error_message": str(e2),
                        "show_tables_error": str(e),
                        "information_schema_error": str(e2)
                    }
                    self.artifacts["errors"].append(error_info)
                    raise Exception(error_msg)
            
            if tables:
                table_names = [table[0] for table in tables[:5]]
                st.write(f"📋 Table names (first 5): {table_names}...")
                if len(tables) > 5:
                    st.write(f"... and {len(tables) - 5} more tables")
            
            schema_dict = {"tables": {}, "relationships": []}
            
            # Get column information for each table
            progress_bar = st.progress(0)
            for i, (table_name, table_type) in enumerate(tables):
                progress_bar.progress((i + 1) / len(tables))
                st.write(f"🔍 Getting columns for table: {table_name}")
                
                try:
                    # Try DESCRIBE TABLE first (more universally supported)
                    cursor.execute(f"DESCRIBE TABLE {table_name}")
                    columns_result = cursor.fetchall()
                    
                    # DESCRIBE TABLE usually returns: name, type, kind, null?, default, primary key, unique key, check, expression, comment
                    columns = []
                    for col_row in columns_result:
                        columns.append({
                            "name": col_row[0],  # Column name
                            "type": col_row[1],  # Data type
                            "nullable": col_row[3] == "Y",  # Nullable
                            "is_identity": False  # Can't easily determine from DESCRIBE
                        })
                    
                    schema_dict["tables"][table_name] = {
                        "type": table_type,
                        "columns": columns
                    }
                    
                except Exception as e:
                    st.warning(f"⚠️ Failed to get columns for table {table_name}: {e}")
                    # Add table with empty columns rather than failing completely
                    schema_dict["tables"][table_name] = {
                        "type": table_type,
                        "columns": []
                    }
                    
                    # Store error in artifacts
                    error_info = {
                        "timestamp": datetime.now().isoformat(),
                        "error_type": "COLUMN_DISCOVERY_ERROR",
                        "error_message": str(e),
                        "table_name": table_name
                    }
                    self.artifacts["errors"].append(error_info)
            
            progress_bar.empty()
            
            # Try to infer relationships from naming conventions
            relationship_count = 0
            for table_name, table_info in schema_dict["tables"].items():
                for column in table_info["columns"]:
                    # Look for potential foreign keys (e.g., user_id that might reference users.id)
                    if "_id" in column["name"].lower():
                        # Extract the potential target table name
                        potential_table = column["name"].lower().replace("_id", "")
                        # Check if the table exists (singular or plural)
                        existing_tables = [t.lower() for t in schema_dict["tables"].keys()]
                        if potential_table in existing_tables or f"{potential_table}s" in existing_tables:
                            target_table = potential_table if potential_table in existing_tables else f"{potential_table}s"
                            schema_dict["relationships"].append({
                                "source_table": table_name,
                                "source_column": column["name"],
                                "target_table": target_table,
                                "inferred": True
                            })
                            relationship_count += 1
            
            if relationship_count > 0:
                st.success(f"🔗 Inferred {relationship_count} potential relationships")
            
            # Store complete schema in artifacts
            self.artifacts["schema"] = {
                "timestamp": datetime.now().isoformat(),
                "table_count": len(schema_dict["tables"]),
                "relationship_count": len(schema_dict["relationships"]),
                "schema_data": schema_dict,
                "database_used": database,
                "schema_used": schema
            }
            
            self.schema = schema_dict
            st.success(f"✅ Schema introspection complete. Found {len(schema_dict['tables'])} tables and inferred {len(schema_dict['relationships'])} relationships.")
            
            return schema_dict
            
        except Exception as e:
            # Make sure any database/connection errors are stored in artifacts
            if "errors" not in self.artifacts:
                self.artifacts["errors"] = []
                
            error_info = {
                "timestamp": datetime.now().isoformat(),
                "error_type": "SCHEMA_INTROSPECTION_ERROR",
                "error_message": str(e),
                "function": "introspect_schema"
            }
            self.artifacts["errors"].append(error_info)
            raise e
            
        finally:
            cursor.close()
    
    # Hierarchical summarization function
    def generate_hierarchical_summary(self, batch_queries: List[Dict]) -> str:
        """Generate structured summary of a batch of queries"""
        if not batch_queries:
            return ""
        
        # Extract key facts from query results
        factual_anchors = []
        for query in batch_queries:
            if 'results_data' in query and query['results_data']:
                # Extract first row of key metrics for fact-checking
                first_result = query['results_data'][0]
                fact_summary = f"Q{query['query_num']}: "
                
                # Look for common metric patterns
                for key, value in first_result.items():
                    if any(keyword in key.lower() for keyword in ['count', 'total', 'unique', 'percentage']):
                        fact_summary += f"{key}={value}, "
                
                if fact_summary != f"Q{query['query_num']}: ":
                    factual_anchors.append(fact_summary.rstrip(', '))
            
        summary_prompt = f"""Based on queries {batch_queries[0]['query_num']} through {batch_queries[-1]['query_num']}, create a structured summary:

CRITICAL: Use these exact numerical facts as anchors for accuracy:
{chr(10).join(factual_anchors)}
        
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
{json.dumps([f"Q{q['query_num']}: {q['sql'][:100]}... -> {q['result_summary']}" for q in batch_queries], indent=2)}

Format as structured text with clear headers, not bullet points. Be concise but comprehensive."""
        
        try:
            summary = self.llm_client.generate(summary_prompt)
            
            # Store the summary generation prompt for debugging
            self.artifacts["thinking_prompts"].append({
                "query_num": f"SUMMARY_{batch_queries[0]['query_num']}-{batch_queries[-1]['query_num']}",
                "timestamp": datetime.now().isoformat(),
                "thinking_prompt": summary_prompt,
                "type": "hierarchical_summary"
            })
            
            return summary
        except Exception as e:
            return f"Error generating summary: {str(e)}"
    
    def generate_llm_prompt(self) -> str:
        """Generate exploration prompt with hierarchical context"""
        prompt = f"""You are an expert data analyst exploring a database to understand its structure, content, and blind spots.

You have run {len(self.query_history)} queries so far, and can run up to {self.max_queries} total queries.

DATABASE SCHEMA:
{json.dumps(self.schema, indent=2)}

EXPLORATION HISTORY:"""
        
        if not self.query_history:
            prompt += "\nThis is the first query.\n"
        else:
            # Use hierarchical summaries for context management
            if self.artifacts["hierarchical_summaries"]:
                prompt += f"""

=== PREVIOUS INSIGHTS (SUMMARIZED) ===
{chr(10).join([f"Batch {i+1}: {summary['summary_content']}" for i, summary in enumerate(self.artifacts["hierarchical_summaries"][-2:])])}

=== CURRENT BATCH FINDINGS ===
Recent findings from current exploration batch:
{json.dumps(self.findings[-5:], indent=2)}
"""
            else:
                # Fallback to current system for first few queries
                prompt += f"""
=== CURRENT FINDINGS ===
{json.dumps(self.findings[:10], indent=2)}
"""
            
            # Show recent query history
            for i, entry in enumerate(self.query_history[-3:]):  # Last 3 queries
                prompt += f"""
=== Query {entry.get('query_num', i+1)} ===
SQL: {entry['sql']}
Result Summary: {entry['result_summary']}
Thinking: {entry.get('thinking', '')}
"""
        
        prompt += f"""
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

Keep SQL concise and efficient."""
        
        # Store prompt in artifacts
        self.artifacts["prompts"].append({
            "query_num": self.query_count + 1,
            "timestamp": datetime.now().isoformat(),
            "prompt_text": prompt
        })
        
        return prompt
    
    def execute_query(self, conn, sql: str) -> pd.DataFrame:
        """Execute SQL query with comprehensive error handling"""
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            df = pd.DataFrame(results, columns=columns)
            return df
        except Exception as e:
            error_info = {
                "query_num": self.query_count + 1,
                "timestamp": datetime.now().isoformat(),
                "error_type": "QUERY_EXECUTION_ERROR",
                "error_message": str(e),
                "sql": sql
            }
            self.artifacts["errors"].append(error_info)
            raise e
        finally:
            cursor.close()
    
    def analyze_results(self, df: pd.DataFrame, sql: str) -> str:
        """Analyze query results with enhanced context"""
        if df.empty:
            summary = "Query returned no results"
            sample_info = "No data to analyze"
        else:
            summary = f"Returned {len(df)} rows, {len(df.columns)} columns"
            
            # Enhanced sample data for analysis
            if len(df) <= 10:
                sample_info = f"All data:\n{df.to_string()}"
            else:
                sample_info = f"Sample (first 5 rows):\n{df.head().to_string()}\n\nData types:\n{df.dtypes.to_string()}"
        
        thinking_prompt = f"""Analyze these SQL results for insights:

SQL Query: {sql}
{summary}

{sample_info}

Provide analysis in this format:
1. What we learned: Key insights from this query
2. Implications: What these results tell us about the data
3. Next directions: What to explore next

Keep it concise."""

        # Store thinking prompt in artifacts
        self.artifacts["thinking_prompts"].append({
            "query_num": self.query_count,
            "timestamp": datetime.now().isoformat(),
            "thinking_prompt": thinking_prompt,
            "sample_data_included": not df.empty
        })
        
        thinking = self.llm_client.generate(thinking_prompt)
        
        # Store thinking response in artifacts
        self.artifacts["thinking_responses"].append({
            "query_num": self.query_count,
            "timestamp": datetime.now().isoformat(),
            "thinking_response": thinking
        })
        
        return thinking
    
    def update_findings(self, thinking: str):
        """Extract findings from thinking with history tracking"""
        lines = thinking.split('\n')
        new_findings_this_query = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                finding_text = line[2:]
                finding_obj = {"finding": finding_text, "timestamp": datetime.now().isoformat()}
                self.findings.append(finding_obj)
                new_findings_this_query.append(finding_obj)
        
        # Store findings evolution in artifacts
        self.artifacts["findings_history"].append({
            "query_num": self.query_count,
            "timestamp": datetime.now().isoformat(),
            "new_findings": new_findings_this_query,
            "total_findings_count": len(self.findings),
            "all_findings_snapshot": copy.deepcopy(self.findings)
        })
    
    # Check if summarization should be triggered
    def should_trigger_summary(self) -> bool:
        """Check if we should generate a summary after this query"""
        return (self.query_count % 3 == 0 and 
                self.query_count >= 3 and 
                len(self.query_history) >= 3)
    
    # Trigger summarization process
    def trigger_hierarchical_summary(self):
        """Generate summary for the last batch of queries"""
        if len(self.query_history) < 3:
            return
            
        # Get the last 3 queries for summarization
        batch_queries = self.query_history[-3:]
        summary = self.generate_hierarchical_summary(batch_queries)
        
        # Store the summary
        summary_data = {
            "batch_range": f"queries_{self.query_count-2}_to_{self.query_count}",
            "timestamp": datetime.now().isoformat(),
            "summary_content": summary,
            "query_count": len(batch_queries),
            "queries_summarized": [q['query_num'] for q in batch_queries]
        }
        
        self.artifacts["hierarchical_summaries"].append(summary_data)
        self.artifacts["summary_trigger_points"].append(self.query_count)
        
        # Optional: Reset findings list to prevent context window bloat
        # Keep only the most recent findings
        if len(self.findings) > 10:
            self.findings = self.findings[-5:]  # Keep last 5 findings
    
    def run_exploration(self, conn) -> str:
        """Main exploration loop with hierarchical summarization"""
        results = []
        
        while self.query_count < self.max_queries:
            try:
                self.query_count += 1
                
                # Generate next query
                prompt = self.generate_llm_prompt()
                llm_response = self.llm_client.generate(prompt)
                
                # Parse LLM response
                if "SQL:" not in llm_response:
                    results.append(f"Query {self.query_count}: Could not parse LLM response")
                    continue
                
                sql_part = llm_response.split("SQL:")[1].split("REASONING:")[0].strip()
                reasoning = llm_response.split("REASONING:")[1].strip() if "REASONING:" in llm_response else "No reasoning provided"
                
                # Execute query
                df = self.execute_query(conn, sql_part)
                result_summary = f"Returned {len(df)} rows, {len(df.columns)} columns"
                
                # Analyze results
                thinking = self.analyze_results(df, sql_part)
                
                # Store query info
                query_info = {
                    "query_num": self.query_count,
                    "sql": sql_part,
                    "reasoning": reasoning,
                    "result_summary": result_summary,
                    "thinking": thinking,
                    "timestamp": datetime.now().isoformat(),
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    "results_data": df.to_dict('records') if len(df) <= 100 else df.head(50).to_dict('records'),
                    "results_truncated": len(df) > 100
                }
                
                self.query_history.append(query_info)
                self.artifacts["query_history"] = copy.deepcopy(self.query_history)
                
                # Update findings
                self.update_findings(thinking)
                
                # Check if we should trigger summarization
                if self.should_trigger_summary():
                    self.trigger_hierarchical_summary()
                    results.append(f"✅ Query {self.query_count}: Generated hierarchical summary for queries {self.query_count-2}-{self.query_count}")
                else:
                    results.append(f"✅ Query {self.query_count}: {result_summary}")
                
            except Exception as e:
                results.append(f"❌ Query {self.query_count}: {str(e)}")
                continue
        
        # Generate final report
        final_report = self.generate_final_report()
        results.append(f"\n📋 **Exploration Complete**: {len(self.query_history)} queries executed, {len(self.artifacts['hierarchical_summaries'])} summaries generated")
        
        return "\n".join(results)
    
    def generate_final_report(self) -> str:
        """Generate final exploration report with artifact capture"""
        # Include summaries in the final report context
        summaries_context = ""
        if self.artifacts["hierarchical_summaries"]:
            summaries_context = f"""

BATCH SUMMARIES GENERATED:
{json.dumps([f"Batch {i+1} ({s['batch_range']}): {s['summary_content'][:200]}..." for i, s in enumerate(self.artifacts["hierarchical_summaries"])], indent=2)}
"""
        
        report_prompt = f"""Generate a summary report of database exploration.

SCHEMA SUMMARY:
- Tables: {len(self.schema.get('tables', {}))}
- Total queries run: {len(self.query_history)}
- Summaries generated: {len(self.artifacts['hierarchical_summaries'])}

{summaries_context}

KEY FINDINGS:
{json.dumps(self.findings[:15], indent=2)}

Generate a markdown report with these sections:
1. Data Structure Overview
2. Key Discoveries  
3. Data Quality Insights
4. Recommendations

Make it concise but actionable."""
        
        report_content = self.llm_client.generate(report_prompt)
        
        # Store final report in artifacts
        self.artifacts["final_report"] = {
            "timestamp": datetime.now().isoformat(),
            "report_prompt": report_prompt,
            "report_content": report_content,
            "total_queries_run": len(self.query_history),
            "total_findings": len(self.findings),
            "total_summaries": len(self.artifacts["hierarchical_summaries"]),
            "session_duration": datetime.now().isoformat()
        }
        
        return report_content

def initialize_session_state():
    """Initialize session state variables"""
    if 'exploration_running' not in st.session_state:
        st.session_state.exploration_running = False
    if 'exploration_results' not in st.session_state:
        st.session_state.exploration_results = None
    if 'llm_provider' not in st.session_state:
        st.session_state.llm_provider = "anthropic"
    if 'datatwin' not in st.session_state:
        st.session_state.datatwin = None
    if 'schema_introspected' not in st.session_state:
        st.session_state.schema_introspected = False
    if 'selected_tables' not in st.session_state:
        st.session_state.selected_tables = []

def load_connection_info():
    """Load connection info from environment"""
    required_vars = [
        'SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USERNAME', 
        'SNOWFLAKE_DATABASE', 'SNOWFLAKE_WAREHOUSE', 'SNOWFLAKE_SCHEMA',
    ]
    
    connection_info = {}
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            connection_info[var] = value
        else:
            missing_vars.append(var)
    
    return connection_info, missing_vars

def render_sidebar():
    """Render sidebar configuration"""
    with st.sidebar:
        st.title("🔍 DataTwin")
        st.markdown("*Autonomous Data Explorer*")
        
        # Show summarization status
        if st.session_state.datatwin and hasattr(st.session_state.datatwin, 'artifacts'):
            summaries = st.session_state.datatwin.artifacts.get('hierarchical_summaries', [])
            if summaries:
                st.success(f"📊 {len(summaries)} summaries generated")
        
        st.divider()
        
        # LLM Provider Selection
        st.subheader("⚙️ Configuration")
        provider = st.selectbox(
            "LLM Provider",
            ["anthropic", "openai"],
            index=0 if st.session_state.llm_provider == "anthropic" else 1,
            help="Choose your preferred LLM provider"
        )
        
        if provider != st.session_state.llm_provider:
            st.session_state.llm_provider = provider
            st.session_state.datatwin = None  # Reset on provider change
        
        # Max queries setting
        max_queries = st.slider(
            "Max Queries", 
            min_value=3, 
            max_value=15, 
            value=7, 
            help="Maximum number of queries to run"
        )
        
        st.divider()
        
        # Connection Status
        st.subheader("🔗 Connection")
        connection_info, missing_vars = load_connection_info()
        
        if missing_vars:
            st.error(f"Missing environment variables: {', '.join(missing_vars)}")
            with st.expander("ℹ️ Required Environment Variables"):
                for var in missing_vars:
                    st.code(f"{var}=your_value")
        else:
            st.success("✅ Connection configured")
            for key, value in connection_info.items():
                if 'PASSWORD' not in key:
                    st.text(f"{key}: {value}")
        
        return connection_info, missing_vars, max_queries

def build_connection_params(connection_info):
    """Build Snowflake connection parameters"""
    conn_params = {
        'account': connection_info['SNOWFLAKE_ACCOUNT'],
        'user': connection_info['SNOWFLAKE_USERNAME'],
        'database': connection_info['SNOWFLAKE_DATABASE'],
        'warehouse': connection_info['SNOWFLAKE_WAREHOUSE'],
        'schema': connection_info['SNOWFLAKE_SCHEMA']
    }

    private_key = os.getenv('NS_PRIVATE_KEY')
    if private_key:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        private_key_obj = serialization.load_pem_private_key(
            private_key.encode(),
            password=None,
            backend=default_backend()
        )
        
        private_key_bytes = private_key_obj.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        conn_params['private_key'] = private_key_bytes
    else:
        conn_params['password'] = os.getenv('SNOWFLAKE_PASSWORD', '')
    
    return conn_params

def render_main_interface(connection_info, missing_vars, max_queries):
    """Render main application interface with table selection"""
    st.title("🔍 DataTwin: Autonomous Data Explorer")
    st.markdown("*Intelligent database exploration with hierarchical insights*")
    
    if missing_vars:
        st.error("Please configure your Snowflake connection in the sidebar first.")
        return
    
    # Step 1: Schema Introspection
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if not st.session_state.schema_introspected:
            if st.button("🔍 Introspect Database Schema", type="primary"):
                with st.spinner("🔄 Discovering database schema..."):
                    try:
                        # Initialize DataTwin for schema introspection only
                        datatwin = StreamlitDataTwin(
                            llm_provider=st.session_state.llm_provider,
                            max_queries=max_queries
                        )
                        
                        # Connect to database
                        conn_params = build_connection_params(connection_info)
                        conn = datatwin.connect_snowflake(conn_params)
                        
                        # Introspect schema
                        schema = datatwin.introspect_schema(conn)
                        conn.close()
                        
                        # Store in session state
                        st.session_state.datatwin = datatwin
                        st.session_state.schema_introspected = True
                        st.session_state.selected_tables = list(schema["tables"].keys())  # Default: all tables
                        
                        st.success("✅ Schema introspection completed!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Schema introspection failed: {str(e)}")
        else:
            st.success("✅ Schema already introspected")
    
    # Step 2: Table Selection (only show if schema is introspected)
    if st.session_state.schema_introspected and st.session_state.datatwin:
        st.divider()
        st.subheader("📊 Select Tables for Exploration")
        
        schema = st.session_state.datatwin.schema
        all_tables = list(schema["tables"].keys())
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.write(f"Found {len(all_tables)} tables in the database:")
            
            # Multi-select for tables
            selected_tables = st.multiselect(
                "Choose tables to explore:",
                options=all_tables,
                default=st.session_state.selected_tables,
                help="Select specific tables to focus your exploration"
            )
            
            # Update session state
            st.session_state.selected_tables = selected_tables
        
        with col2:
            # Quick selection buttons
            if st.button("Select All"):
                st.session_state.selected_tables = all_tables
                st.rerun()
            
            if st.button("Clear All"):
                st.session_state.selected_tables = []
                st.rerun()
        
        with col3:
            # Show selection stats
            st.metric("Selected", len(selected_tables))
            st.metric("Total", len(all_tables))
        
        # Show table details for selected tables
        if selected_tables:
            with st.expander(f"📋 Preview Selected Tables ({len(selected_tables)})"):
                for table_name in selected_tables[:5]:  # Show first 5
                    table_info = schema["tables"][table_name]
                    st.write(f"**{table_name}** ({table_info['type']}) - {len(table_info['columns'])} columns")
                
                if len(selected_tables) > 5:
                    st.write(f"... and {len(selected_tables) - 5} more tables")
    
    # Step 3: Start Exploration (only show if tables are selected)
    if st.session_state.schema_introspected and st.session_state.selected_tables:
        st.divider()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button(
                f"🚀 Start Exploration ({len(st.session_state.selected_tables)} tables)",
                disabled=st.session_state.exploration_running,
                type="primary"
            ):
                st.session_state.exploration_running = True
                
                with st.spinner("🔄 Exploring selected tables..."):
                    try:
                        # Use existing datatwin but filter schema to selected tables
                        datatwin = st.session_state.datatwin
                        
                        # Filter schema to selected tables only
                        filtered_schema = {
                            "tables": {
                                table: datatwin.schema["tables"][table] 
                                for table in st.session_state.selected_tables
                            },
                            "relationships": [
                                rel for rel in datatwin.schema.get("relationships", [])
                                if rel["source_table"] in st.session_state.selected_tables
                                and rel["target_table"] in st.session_state.selected_tables
                            ]
                        }
                        
                        # Update the datatwin's schema
                        datatwin.schema = filtered_schema
                        
                        # Connect and run exploration
                        conn_params = build_connection_params(connection_info)
                        conn = datatwin.connect_snowflake(conn_params)
                        
                        results = datatwin.run_exploration(conn)
                        conn.close()
                        
                        # Store results
                        st.session_state.exploration_results = results
                        
                        st.success("✅ Exploration completed!")
                        
                    except Exception as e:
                        st.error(f"❌ Exploration failed: {str(e)}")
                    finally:
                        st.session_state.exploration_running = False
        
        with col2:
            if st.session_state.datatwin:
                st.metric(
                    "Queries Run", 
                    len(st.session_state.datatwin.query_history),
                    help="Total SQL queries executed"
                )

def render_results():
    """Render exploration results with enhanced summaries display"""
    if not st.session_state.datatwin:
        st.info("👆 Run an exploration to see results")
        return
    
    datatwin = st.session_state.datatwin
    
    # Enhanced tabs with summaries
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Report", 
        "🔍 Queries", 
        "📊 Summaries",
        "🏗️ Schema", 
        "⬇️ Downloads"
    ])
    
    with tab1:
        st.subheader("📋 Exploration Report")
        if datatwin.artifacts.get("final_report", {}).get("report_content"):
            st.markdown(datatwin.artifacts["final_report"]["report_content"])
        else:
            st.info("Report will be generated after exploration completes")
    
    with tab2:
        st.subheader("🔍 Query History")
        for i, query in enumerate(datatwin.query_history):
            with st.expander(f"Query {query['query_num']}: {query['sql'][:50]}..."):
                st.code(query['sql'], language='sql')
                st.write("**Reasoning:**", query.get('reasoning', 'N/A'))
                st.write("**Results:**", query['result_summary'])
                if query.get('thinking'):
                    st.write("**Analysis:**")
                    st.write(query['thinking'])
    
    # Summaries Tab
    with tab3:
        st.subheader("📊 Hierarchical Summaries")
        summaries = datatwin.artifacts.get('hierarchical_summaries', [])
        
        if summaries:
            st.info(f"Generated {len(summaries)} batch summaries during exploration")
            
            for i, summary in enumerate(summaries):
                with st.expander(f"📊 Summary {i+1}: {summary['batch_range']} ({summary['query_count']} queries)"):
                    st.markdown(summary['summary_content'])
                    st.caption(f"Generated: {summary['timestamp']}")
                    
                    # Show which queries were summarized
                    if 'queries_summarized' in summary:
                        st.write("**Queries summarized:**", ", ".join(map(str, summary['queries_summarized'])))
        else:
            st.info("Summaries will appear after 3+ queries are executed")
            st.write("The system generates hierarchical summaries every 3 queries to maintain context efficiency.")
    
    with tab4:
        st.subheader("🏗️ Database Schema")
        if datatwin.schema:
            for table_name, table_info in datatwin.schema["tables"].items():
                with st.expander(f"📊 {table_name} ({table_info['type']})"):
                    columns_df = pd.DataFrame(table_info["columns"])
                    st.dataframe(columns_df, width='stretch')
        else:
            st.info("Schema information will appear here")
    
    with tab5:
        st.subheader("⬇️ Download Results")
        
        if datatwin.artifacts:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.download_button(
                    "📄 Complete Report",
                    datatwin.artifacts["final_report"].get("report_content", ""),
                    "datatwin_report.md",
                    "text/markdown"
                )
            
            with col2:
                # Fix: Use convert_decimals to handle Timestamp objects
                query_history_json = json.dumps(convert_decimals(datatwin.query_history), indent=2)
                st.download_button(
                    "🔍 Query History", 
                    query_history_json,
                    "datatwin_queries.json",
                    "application/json"
                )
            
            with col3:
                # Fix: Use convert_decimals to handle all artifacts
                artifacts_json = json.dumps(convert_decimals(datatwin.artifacts), indent=2)
                st.download_button(
                    "🗃️ Complete Artifacts",
                    artifacts_json,
                    "datatwin_artifacts.json", 
                    "application/json"
                )
            
            # Summaries download
            with col4:
                summaries = datatwin.artifacts.get('hierarchical_summaries', [])
                if summaries:
                    # Fix: Use convert_decimals for summaries too
                    summaries_json = json.dumps(convert_decimals(summaries), indent=2)
                    st.download_button(
                        "📊 Summaries Only",
                        summaries_json,
                        "datatwin_summaries.json",
                        "application/json"
                    )
                else:
                    st.button("📊 No Summaries", disabled=True)

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="DataTwin Explorer", 
        page_icon="🔍", 
        layout="wide"
    )
    
    initialize_session_state()
    connection_info, missing_vars, max_queries = render_sidebar()
    render_main_interface(connection_info, missing_vars, max_queries)
    render_results()

if __name__ == "__main__":
    main()