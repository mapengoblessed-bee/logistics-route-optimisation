/**
 * script.js
 * ---------
 * Client-side interactivity for Logistics Route Optimization DSS:
 * - Dynamic depot / destination checkbox synchronization
 * - AJAX optimization and instant UI updating
 * - In-place distance matrix editing and batch saving
 * - Route visualization and Decision Analysis updating
 * - Mathematical Model & Academic Guide Modal control
 */

document.addEventListener("DOMContentLoaded", function () {
    const optForm = document.getElementById("optimizationForm");
    if (optForm) {
        optForm.addEventListener("submit", handleOptimizationSubmit);
    }
});

/**
 * Syncs the depot dropdown with the destination checkboxes.
 * Prevents selecting the depot as a delivery stop.
 */
function handleDepotChange() {
    const depotSelect = document.getElementById("depot_id");
    const selectedDepotId = depotSelect.value;
    const items = document.querySelectorAll(".checkbox-item");

    items.forEach(item => {
        const checkbox = item.querySelector("input[type='checkbox']");
        const badge = item.querySelector(".loc-badge");
        const locId = checkbox.value;

        if (locId === selectedDepotId) {
            checkbox.checked = false;
            checkbox.disabled = true;
            item.classList.add("depot-disabled");
            if (badge) badge.textContent = "Depot";
        } else {
            checkbox.disabled = false;
            item.classList.remove("depot-disabled");
            if (badge) badge.textContent = "Delivery";
        }
    });
}

/**
 * Select all non-depot destinations.
 */
function selectAllDestinations() {
    const depotSelect = document.getElementById("depot_id");
    const selectedDepotId = depotSelect.value;
    const checkboxes = document.querySelectorAll("input[name='delivery_ids']");

    checkboxes.forEach(cb => {
        if (cb.value !== selectedDepotId) {
            cb.checked = true;
        }
    });
}

/**
 * Clear all destinations.
 */
function clearAllDestinations() {
    const checkboxes = document.querySelectorAll("input[name='delivery_ids']");
    checkboxes.forEach(cb => {
        cb.checked = false;
    });
}

/**
 * Handle form submission via AJAX for instant reactivity.
 */
async function handleOptimizationSubmit(e) {
    e.preventDefault();

    const depotId = document.getElementById("depot_id").value;
    const fuelPrice = parseFloat(document.getElementById("fuel_price").value);
    const fuelConsumption = parseFloat(document.getElementById("fuel_consumption").value);

    const checkedBoxes = Array.from(document.querySelectorAll("input[name='delivery_ids']:checked"));
    const deliveryIds = checkedBoxes.map(cb => parseInt(cb.value)).filter(id => id !== parseInt(depotId));

    if (deliveryIds.length === 0) {
        showAlert("Please select at least one delivery destination different from the depot.", "error");
        return;
    }

    if (isNaN(fuelPrice) || fuelPrice <= 0) {
        showAlert("Please enter a valid positive fuel price.", "error");
        return;
    }

    if (isNaN(fuelConsumption) || fuelConsumption <= 0) {
        showAlert("Please enter a valid positive fuel consumption rate.", "error");
        return;
    }

    const btn = document.getElementById("btnOptimize");
    const originalText = btn.innerHTML;
    btn.innerHTML = `<svg class="spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg> Optimizing...`;
    btn.disabled = true;

    try {
        const response = await fetch("/optimize", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                depot_id: depotId,
                delivery_ids: deliveryIds,
                fuel_price: fuelPrice,
                fuel_consumption: fuelConsumption
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            showAlert(data.error || "Optimization failed.", "error");
            btn.innerHTML = originalText;
            btn.disabled = false;
            return;
        }

        // Render updated results
        updateResultsUI(data, fuelConsumption, fuelPrice);
        showAlert("Route successfully optimized using Google OR-Tools!", "info");

    } catch (err) {
        console.error("Optimization error:", err);
        showAlert("An error occurred while connecting to the optimization engine.", "error");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

/**
 * Updates all DOM elements with the new optimization results.
 */
function updateResultsUI(data, fuelConsumption, fuelPrice) {
    const opt = data.optimal_route;
    const orig = data.original_route;
    const comp = data.comparison;

    // 1. Status banner
    const statusText = document.getElementById("statusText");
    if (statusText) statusText.textContent = data.status || "Optimal Solution Found";

    // 2. Summary cards
    const valDist = document.getElementById("valTotalDistance");
    if (valDist) valDist.innerHTML = `${opt.total_distance_km} <span class="unit">km</span>`;

    const valFuel = document.getElementById("valFuelUsed");
    if (valFuel) valFuel.innerHTML = `${opt.total_fuel_litres} <span class="unit">Litres</span>`;

    const valCost = document.getElementById("valFuelCost");
    if (valCost) valCost.textContent = `$${opt.total_fuel_cost.toFixed(2)}`;

    const valPct = document.getElementById("valPctReduction");
    if (valPct) valPct.textContent = `${comp.percentage_reduction}%`;

    // 3. Optimal sequence text
    const seqDisplay = document.getElementById("optimalRouteDisplay");
    if (seqDisplay) seqDisplay.textContent = opt.route_display;

    // 4. Visual Flowchart
    const container = document.getElementById("routeNodesContainer");
    if (container) {
        container.innerHTML = "";
        opt.route_names.forEach((name, idx) => {
            const isDepot = (idx === 0 || idx === opt.route_names.length - 1);
            
            // Node
            const nodeDiv = document.createElement("div");
            nodeDiv.className = `route-node ${isDepot ? 'depot-node' : ''}`;
            nodeDiv.innerHTML = `
                <div class="node-circle">
                    ${isDepot ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>' : idx}
                </div>
                <div class="node-label">${escapeHtml(name)}</div>
            `;
            container.appendChild(nodeDiv);

            // Edge
            if (idx < opt.route_names.length - 1) {
                const leg = opt.legs[idx];
                const edgeDiv = document.createElement("div");
                edgeDiv.className = "route-edge";
                edgeDiv.innerHTML = `
                    <div class="edge-line"></div>
                    <div class="edge-info">${leg.distance_km} km<br><span>$${leg.fuel_cost.toFixed(2)}</span></div>
                    <div class="edge-arrow">&rarr;</div>
                `;
                container.appendChild(edgeDiv);
            }
        });
    }

    // 5. Comparison Table (Decision Analysis)
    setText("compOrigDist", `${orig.total_distance_km} km`);
    setText("compOptDist", `${opt.total_distance_km} km`);
    setText("compSavedDist", `- ${comp.distance_saved_km} km`);
    setText("compPctDist", `${comp.percentage_reduction}%`);

    setText("compOrigFuel", `${orig.total_fuel_litres} L`);
    setText("compOptFuel", `${opt.total_fuel_litres} L`);
    setText("compSavedFuel", `- ${comp.fuel_saved_litres} L`);

    setText("compOrigCost", `$${orig.total_fuel_cost.toFixed(2)}`);
    setText("compOptCost", `$${opt.total_fuel_cost.toFixed(2)}`);
    setText("compSavedCost", `- $${comp.cost_saved.toFixed(2)}`);
    setText("compPctCost", `-${comp.percentage_reduction}%`);

    setText("compExplanation", comp.explanation);

    // 6. Detailed legs table
    const legsTbody = document.getElementById("legsTableBody");
    if (legsTbody) {
        legsTbody.innerHTML = "";
        opt.legs.forEach(leg => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><span class="leg-pill">${leg.step}</span></td>
                <td><strong>${escapeHtml(leg.origin_name)}</strong></td>
                <td><strong>${escapeHtml(leg.destination_name)}</strong></td>
                <td>${leg.distance_km} km</td>
                <td>${leg.fuel_litres} L</td>
                <td class="leg-cost">$${leg.fuel_cost.toFixed(2)}</td>
            `;
            legsTbody.appendChild(tr);
        });
    }

    setText("footerDist", `${opt.total_distance_km} km`);
    setText("footerFuel", `${opt.total_fuel_litres} L`);
    setText("footerCost", `$${opt.total_fuel_cost.toFixed(2)}`);
}

function setText(elementId, text) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = text;
}

function escapeHtml(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

/**
 * Highlights a distance table cell when the user changes its value.
 */
function markCellModified(input) {
    input.classList.add("modified");
}

/**
 * Saves all modified distance values in the database.
 */
async function saveDistanceMatrix() {
    const inputs = document.querySelectorAll(".cell-input");
    const distances = [];

    inputs.forEach(inp => {
        const origId = inp.dataset.origin;
        const destId = inp.dataset.dest;
        const val = parseFloat(inp.value);

        if (!isNaN(val) && val >= 0) {
            distances.push({
                origin_id: parseInt(origId),
                destination_id: parseInt(destId),
                distance_km: val
            });
        }
    });

    if (distances.length === 0) {
        showAlert("No valid distance data to save.", "error");
        return;
    }

    const btn = document.getElementById("btnSaveDistances");
    const origText = btn.textContent;
    btn.textContent = "Saving...";
    btn.disabled = true;

    try {
        const response = await fetch("/update_all_distances", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ distances: distances })
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showAlert("Distance matrix successfully updated in database!", "info");
            document.querySelectorAll(".cell-input.modified").forEach(el => el.classList.remove("modified"));
            
            // Automatically re-run optimization with new distances
            const optForm = document.getElementById("optimizationForm");
            if (optForm) {
                optForm.dispatchEvent(new Event("submit"));
            }
        } else {
            showAlert(data.error || "Failed to save distances.", "error");
        }
    } catch (err) {
        console.error("Save error:", err);
        showAlert("Error saving distances to database.", "error");
    } finally {
        btn.textContent = origText;
        btn.disabled = false;
    }
}

/**
 * Resets database and distance table to factory sample data.
 */
async function resetDefaults() {
    if (!confirm("Are you sure you want to reset all locations and distances to factory sample values?")) {
        return;
    }

    try {
        const response = await fetch("/reset_distances", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();
        if (response.ok && data.success) {
            window.location.reload();
        } else {
            showAlert("Failed to reset defaults.", "error");
        }
    } catch (err) {
        console.error("Reset error:", err);
        showAlert("Error resetting database defaults.", "error");
    }
}

/**
 * Displays an alert banner at the top of the dashboard.
 */
function showAlert(message, type = "info") {
    const alertBox = document.getElementById("alertBox");
    if (!alertBox) return;

    alertBox.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    alertBox.classList.remove("hidden");

    setTimeout(() => {
        alertBox.classList.add("hidden");
    }, 6000);
}

/**
 * Toggles the academic explanation and mathematical model modal.
 */
function toggleTheoryModal() {
    const modal = document.getElementById("theoryModal");
    if (!modal) return;
    modal.classList.toggle("hidden");
}
