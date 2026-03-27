# SMT Solver Travel Planning

A hybrid travel itinerary planner that uses natural language constraints, LLM-based code generation, and Z3 optimization to solve multi-city travel planning problems.

## 🔎 Project Overview

- **Input**: user query (text constraints + persona + destination/origin/dates)
- **Pipeline**:
  1. Normalize with LLM prompt (role: turn query into JSON)
  2. Convert constraints → planning steps via LLM (e.g., destination, departure, transportation, budget)
  3. Convert steps → Python code templates via LLM prompts
  4. Append hard-coded solve routine (`prompts/solve_{3,5,7}.txt`)
  5. Execute generated code with Z3 solver (`z3` Optimize/Solver)
  6. Extract and print plan in structured form
- **Output**: itinerary with cities, transport, restaurants, attractions, accommodations, total costs and schedule.

## 📁 Repo Structure

- `Test_TravelPlanner.py`: main workflow and pipeline implementation.
- `tools/`: API wrapper modules for external data fetching.
  - `cities/apis.py`
  - `flights/apis.py`
  - `accommodations/apis.py`
  - `attractions/apisv3.py`
  - `googleDistanceMatrix/apis.py`
  - `restaurants/apis.py`
- `prompts/`: prompt templates for LLM stages.
- `utils/`: helper logic (budget, selection, etc.).
- `openai_func.py` / `open_source_models.py`: LLM integration utilities.
- `requirements.txt`: Python dependencies.
- `output/`: generated run outputs (plans, codes, logs).

## ⚙️ Installation

1. Clone the repo:
   ```bash
   git clone <repo-url>
   cd SMT_Solver_Travel_Planning
   ```
   After cloning the repo put the tripcraft database in the root folder. For database refer to the drive link in the Email.

   ---
2. Create and activate a Python environment:

- Using `conda` (env name `fmtravelplanner`):
   ```bash
   conda create -n fmtravelplanner python=3.11 -y
   conda activate fmtravelplanner
   ```

3. Install deps:
   ```bash
   pip install -r requirements.txt
   ```

4. API keys (if you want real external API behavior):
   - `HUGGING_FACE_TOKEN`

## ▶️ Usage

### 1. Running end-to-end planner

```bash
python Test_TravelPlanner.py --set_type 3d --model_name phi
```

**Arguments:**
- `--set_type`: Dataset type to use
  - `3d`: Use tripcraft_3day.csv dataset
  - `5d`: Use tripcraft_5day.csv dataset
  - `7d`: Use tripcraft_7day.csv dataset
  - Default: `3d`
- `--model_name`: LLM model to use for code generation
  - `gpt`: OpenAI GPT models
  - `qwen`: Qwen model
  - `phi`: Phi model
  - `llama`: Llama model
  - `mistral`: Mistral model
  - Default: `gpt`

### 2. Output location
- `output/<set_type>/<model_name>_nl/<index>/plans/`
- `output/<set_type>/<model_name>_nl/<index>/codes/`

