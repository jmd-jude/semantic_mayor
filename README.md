# DataTwin Explorer 🔍

An autonomous data exploration tool that uses AI to intelligently discover insights, patterns, and data quality issues in your Snowflake database. DataTwin combines automated SQL generation with hierarchical summarization to provide comprehensive database analysis.

## Features

- **Autonomous Exploration**: AI-driven SQL query generation for intelligent data discovery
- **Multi-LLM Support**: Works with both Anthropic Claude and OpenAI GPT models
- **Hierarchical Summarization**: Efficient context management through batch summarization
- **Interactive Table Selection**: Choose specific tables to focus your exploration
- **Schema Introspection**: Automatic discovery of database structure and relationships
- **Data Quality Analysis**: Identifies patterns, anomalies, and data completeness issues
- **Comprehensive Reporting**: Generates structured insights and recommendations

## Quick Start

### Prerequisites

- Python 3.8+
- Snowflake account with appropriate permissions
- API key for either Anthropic Claude or OpenAI

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/datatwin-explorer.git
cd datatwin-explorer
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root with your credentials:

```env
# Snowflake Configuration
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USERNAME=your_username
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_SCHEMA=your_schema

# Optional: Private Key Authentication
# NS_PRIVATE_KEY=your_private_key_pem_content

# LLM API Keys (choose one or both)
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
```

### Running the Application

```bash
streamlit run app.py
```

Navigate to `http://localhost:8501` to access the web interface.

## How It Works

### 1. Schema Introspection
DataTwin automatically discovers your database structure, including:
- Table schemas and column types
- Inferred relationships between tables
- Data type analysis

### 2. Intelligent Exploration
The AI agent generates SQL queries to:
- Understand data distributions and patterns
- Identify relationships between tables
- Discover data quality issues
- Find business insights

### 3. Hierarchical Summarization
To manage context efficiently:
- Generates summaries every 3 queries
- Maintains key insights while reducing token usage
- Preserves important discoveries across exploration sessions

### 4. Comprehensive Reporting
Produces structured reports with:
- Data structure overview
- Key discoveries and patterns
- Data quality assessments
- Actionable recommendations

## Usage Guide

### Basic Workflow

1. **Configure Connection**: Set up your Snowflake credentials in the sidebar
2. **Introspect Schema**: Click "Introspect Database Schema" to discover your database structure
3. **Select Tables**: Choose specific tables to focus your exploration
4. **Start Exploration**: Launch the autonomous exploration process
5. **Review Results**: Analyze findings through the interactive interface

### Advanced Features

#### Table Selection
- Select specific tables for targeted analysis
- Use "Select All" or "Clear All" for quick selection
- Preview selected tables before exploration

#### LLM Provider Selection
- Choose between Anthropic Claude or OpenAI GPT
- Configure maximum number of queries (3-15)
- Provider can be changed between sessions

#### Download Options
- Complete exploration report (Markdown)
- Query history (JSON)
- Hierarchical summaries (JSON)
- Complete artifacts with metadata (JSON)

## Architecture

### Core Components

- **StreamlitDataTwin**: Main exploration engine with hierarchical summarization
- **LLMClient**: Unified interface for multiple LLM providers
- **Schema Introspection**: Database structure discovery
- **Query Generation**: AI-driven SQL creation
- **Results Analysis**: Intelligent insight extraction
- **Artifact Management**: Comprehensive session tracking

### Key Features

#### Hierarchical Summarization
- Prevents context window overflow
- Maintains exploration continuity
- Preserves critical insights
- Enables longer exploration sessions

#### Error Handling
- Comprehensive error capture and logging
- Graceful degradation on connection issues
- Detailed error reporting in artifacts

#### Security
- Environment variable configuration
- Support for private key authentication
- No credential storage in artifacts

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SNOWFLAKE_ACCOUNT` | Yes | Your Snowflake account identifier |
| `SNOWFLAKE_USERNAME` | Yes | Snowflake username |
| `SNOWFLAKE_DATABASE` | Yes | Target database name |
| `SNOWFLAKE_WAREHOUSE` | Yes | Snowflake warehouse |
| `SNOWFLAKE_SCHEMA` | Yes | Target schema name |
| `NS_PRIVATE_KEY` | Conditional | Private key |
| `ANTHROPIC_API_KEY` | Optional | Anthropic Claude API key |
| `OPENAI_API_KEY` | Optional | OpenAI API key |

### Application Settings

- **Max Queries**: 3-15 (default: 7)
- **LLM Provider**: Anthropic Claude or OpenAI GPT
- **Summarization Frequency**: Every 3 queries
- **Results Limit**: 100 rows per query (first 50 for large results)

## Troubleshooting

### Common Issues

#### Connection Problems
- Verify Snowflake credentials and permissions
- Check network connectivity
- Ensure warehouse is running

#### Schema Access Issues
- Confirm database and schema permissions
- Verify object names match exactly
- Check role assignments

#### LLM API Issues
- Validate API keys
- Check rate limits
- Verify network access to API endpoints

### Error Logging
All errors are captured in the artifacts structure:
- Connection errors
- Query execution failures
- Schema introspection issues
- LLM API problems

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Commit your changes: `git commit -am 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Create an issue for bug reports or feature requests
- Check the troubleshooting section for common problems
- Review the artifacts JSON for detailed error information

## Roadmap

- [ ] Support for additional database providers
- [ ] Enhanced visualization capabilities
- [ ] Custom exploration templates
- [ ] Advanced relationship discovery
- [ ] Performance optimization for large schemas
- [ ] Integration with data catalog tools

---

**DataTwin Explorer** - Intelligent autonomous data exploration powered by AI