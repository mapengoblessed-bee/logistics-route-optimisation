# Logistics Route Optimization Decision Support System (DSS)

An interactive, web-based **Decision Support System (DSS)** designed to assist logistics and fleet managers in identifying the most cost-effective delivery routes using mathematical optimization under conditions of certainty.

The application formulates delivery routing as a **Travelling Salesperson Problem (TSP)** and solves it using **Google OR-Tools**, minimizing total transportation fuel costs based on deterministic distances, vehicle fuel consumption rates, and fixed fuel prices.

---

## 1. Project Overview & DSS Objectives

In distribution and supply chain management, choosing an arbitrary or intuition-based delivery sequence often results in excessive mileage, elevated fuel expenses, and unnecessary vehicle wear. 

This DSS provides an objective, data-driven analytical tool that:
1. **Models Decision-Making Under Certainty:** Operates on known, deterministic road distances, vehicle fuel consumption rates, and fuel prices.
2. **Evaluates Routing Alternatives:** Compares the baseline (unoptimized sequential route) against the mathematically optimal sequence.
3. **Quantifies Managerial Value:** Displays total distance saved (km), fuel saved (litres), cost savings ($), and percentage cost reduction.
4. **Allows Sensitivity Analysis:** Enables managers to modify distance values, fuel consumption, and fuel prices to observe real-time cost impacts.

---

## 2. Mathematical Model Formulation

The system models the delivery operation as a **Travelling Salesperson Problem (TSP)** with a single vehicle and fixed start/end depot.

### Objective Function

$$\text{Minimize } Z = \sum_{i=0}^{N-1} \sum_{j=0}^{N-1} C_{ij} \times X_{ij}$$

Where:
- $Z$ = Total transportation fuel cost for the completed delivery tour (\$).
- $C_{ij}$ = Fuel cost of travelling directly from location $i$ to location $j$ (\$).
- $X_{ij}$ = Binary decision variable:
  $$X_{ij} = \begin{cases} 1 & \text{if the vehicle travels directly from location } i \text{ to } j \\ 0 & \text{otherwise} \end{cases}$$

### Leg Transportation Cost Formula

$$C_{ij} = D_{ij} \times \left(\frac{F}{100}\right) \times P$$

Where:
- $D_{ij}$ = Shortest road distance between location $i$ and location $j$ in kilometres.
- $F$ = Vehicle fleet fuel consumption in litres per 100 kilometres ($L/100\text{ km}$).
- $P$ = Unit fuel price per litre (\$/litre).

### Operational Constraints

1. **Depot Departure and Return:** The delivery vehicle begins at the selected central depot and must return to that same depot upon completing all deliveries:
   $$\sum_{j=1}^{N-1} X_{\text{depot}, j} = 1 \quad \text{and} \quad \sum_{i=1}^{N-1} X_{i, \text{depot}} = 1$$
2. **Single Visit Constraint:** Every designated customer delivery location $j$ must be visited exactly once:
   $$\sum_{i=0, i \neq j}^{N-1} X_{ij} = 1 \quad \forall j \in \{1, \dots, N-1\}$$
3. **Single Departure Constraint:** The vehicle departs from each visited location exactly once:
   $$\sum_{j=0, j \neq i}^{N-1} X_{ij} = 1 \quad \forall i \in \{1, \dots, N-1\}$$
4. **Subtour Elimination:** Prevents disjoint secondary loops, ensuring one continuous Hamiltonian cycle connecting all chosen destinations and the depot.
5. **Non-Negativity:** Distances $D_{ij} \ge 0$, fuel consumption $F > 0$, and fuel price $P > 0$.

---

## 3. How Google OR-Tools Solves the Problem

The optimization engine (`optimizer.py`) utilizes the Google Operations Research Tools (`ortools.constraint_solver`):

1. **`RoutingIndexManager`**: Maps solver node indices to actual location IDs, tracking the single vehicle and designated depot node.
2. **`RoutingModel`**: Enforces TSP Hamiltonian cycle constraints, flow balance, and single-visit requirements.
3. **Arc Cost Evaluator**: Registers a callback function that returns the exact transportation cost $C_{ij}$ in integer cents (or distance in meters). Because $(F / 100) \times P$ is a strictly positive linear multiplier, minimizing cost is mathematically congruent to minimizing distance while accounting for pricing parameters.
4. **First Solution Strategy (`PATH_CHEAPEST_ARC`)**: Rapidly generates an initial feasible tour by iteratively choosing the cheapest valid outbound arc.
5. **Local Search Metaheuristic (`GUIDED_LOCAL_SEARCH`)**: Intelligently escapes local minima by penalizing frequently traversed edges, converging upon the globally optimal delivery tour.

---

## 4. Technology Stack & Architecture

- **Backend:** Python 3.10+ / 3.13, Flask 3.1
- **Optimization:** Google OR-Tools 9.15
- **Database:** SQLite 3 (self-contained, zero-configuration)
- **Frontend:** Semantic HTML5, CSS3, Vanilla JavaScript (Fetch API)

### File Structure

```
ROUTE OPT/
├── app.py                # Main Flask application and REST routes
├── optimizer.py          # Google OR-Tools mathematical TSP solver
├── database.py           # SQLite database schema, defaults & queries
├── requirements.txt      # Project dependencies
├── test_app.py           # Automated test suite (8 unit tests)
├── templates/
│   └── index.html        # Clean, modern single-page dashboard UI
└── static/
    ├── style.css         # Modern styling (dark-blue header, crisp cards)
    └── script.js         # Interactive form handling, AJAX, live updates
```

---

## 5. Getting Started (Visual Studio Code Instructions)

### Step 1: Open the Project in VS Code
1. Launch **Visual Studio Code**.
2. Select **File > Open Folder...** and choose the `ROUTE OPT` directory.

### Step 2: Open Terminal in VS Code
Open an integrated terminal by pressing:
- **Ctrl + `** (backtick) or selecting **Terminal > New Terminal**.

### Step 3: Install Required Packages
In the terminal, run:
```powershell
pip install -r requirements.txt
```
*(Dependencies: `Flask` and `ortools`)*

### Step 4: Run the Application
Run the Flask server:
```powershell
python app.py
```

### Step 5: View the Dashboard
Open your web browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 6. Running Automated Tests

To run the automated test suite verifying the database, calculations, OR-Tools optimizer, and Flask endpoints:

```powershell
python -m unittest test_app.py
```

Expected output:
```
Ran 8 tests in ~8.9s
OK
```

---

## 7. Sample Demonstration Walkthrough (For Academic Presentation)

When demonstrating this system to a lecturer or examiner:

1. **Initial Dashboard State:**
   - Note the default Zimbabwean distribution hub: **Depot (Starting Point)** near Harare, servicing customer locations in **Harare, Bulawayo, Gweru, Mutare, and Masvingo**.
   - Review the preloaded fuel parameters (\$1.65 / Litre, 28.0 L / 100 km).

2. **Observe Decision Analysis (Comparison Section):**
   - **Original / Default Delivery Route:** Depot $\to$ Harare $\to$ Bulawayo $\to$ Gweru $\to$ Mutare $\to$ Masvingo $\to$ Depot (Total Distance: **2,153 km**, Cost: **\$994.69**).
   - **Optimized Delivery Route:** Depot $\to$ Harare $\to$ Mutare $\to$ Masvingo $\to$ Bulawayo $\to$ Gweru $\to$ Depot (Total Distance: **1,301 km**, Cost: **\$601.06**).
   - **Demonstrate Value:** The DSS saves **852 km** and **\$393.63 in fuel** (**39.57% cost reduction**) on a single delivery trip!

3. **Demonstrate Interactivity & Sensitivity Analysis:**
   - **Select Subsets:** Deselect one or two cities (e.g. uncheck Mutare and Masvingo) and click **"Find Optimal Route"**. Observe how the route dynamically recalculates instantly without a full page reload.
   - **Change Depot:** Change the Starting Depot to **Bulawayo**. Notice how the destinations adapt automatically.
   - **Edit Distances:** In the **Distance Matrix** table, change a distance value (e.g., set Bulawayo $\to$ Mutare to 500 km) and click **"Save Distances"**. The system persists the changes in SQLite and refreshes the optimal tour.
   - **Reset Sample Data:** Click **"Reset Defaults"** to restore factory sample distances.

4. **Academic Justification:**
   - Click the **"Mathematical Model & DSS Guide"** button in the header to display the mathematical formulation, objective function, and OR-Tools algorithmic description for the examiner.
