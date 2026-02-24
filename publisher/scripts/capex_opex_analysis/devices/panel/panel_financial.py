
from capex_opex_analysis.financial_report_graphs import *
from itertools import combinations


#--------------------------------------------------------------------Create Panels Report-------------------------------------------------------------------------------
def panel_capex_opex_report(df_panels, p):
   
    df_panels_locations = calculate_panels_location(p, df_panels)
    
    fin_general = p.financial.general
    fin_panel = p.financial.devices.panel
    comm = fin_panel.active_communication
    fields = p.simulation.devices.panel.database.fields
    n_panels = int(df_panels[fields.panel_num].max())

    # CAPEX (Capital Expediture) ------------------------------------------------------------------
    total_panel_price = n_panels * comm.price_per_panel
    total_installation_price = n_panels * comm.price_panel_installation

    total_cables_size = calculate_cables_size(df_panels, df_panels_locations, p)
    total_cables_price = total_cables_size * comm.price_cable_meter
    total_cables_installation_price = total_cables_size * comm.price_cable_installation_meter

    capex_total = total_panel_price + total_installation_price + total_cables_price + total_cables_installation_price

    # OPEX (Operational Expediture) -----------------------------------------------------------------
    annual_maintenance_price = n_panels * comm.price_panel_annual_maintenance
    annual_energy_price = n_panels * (24 * 365) * (comm.panel_power_W / 1000) * fin_general.price_kWh

    opex_annual_cost = annual_maintenance_price + annual_energy_price 

    #----------------------------------------------------------------------------------------------
    # Organize os dados em um dicionário
    data_output = {
        "Number of Panels": [n_panels],
        "Total Panel Price": [total_panel_price],
        "Total Installation Price": [total_installation_price],
        "Total Cable Size (meters)": [total_cables_size],
        "Total Cable Price": [total_cables_price],
        "Total Cable Installation Price": [total_cables_installation_price],
        "Total Investment Price":[capex_total],
        "Annual Maintenance Price": [annual_maintenance_price],
        "Annual Energy Price": [annual_energy_price],
        "Total Annual Opex Cost": [opex_annual_cost]
    }

    data_output = pd.DataFrame(data_output)

    # Transpose the DataFrame
    data_output_transposed = pd.DataFrame({"Variables": data_output.columns,"Values": data_output.iloc[0]})
    data_output_transposed["Values"] = data_output_transposed["Values"].round()
    data_output_transposed.to_csv(f"{fin_general.save_report_path}/panel_financial_report.csv", index=False)

    panel_graphs(data_output_transposed, p)
    print(f"Panel financial report saved to {fin_general.save_report_path}/panel_financial_report.csv")


    return data_output_transposed



def panel_graphs(df, p):
    fin_general = p.financial.general
    fin_panel = p.financial.devices.panel

    if fin_panel.enable_capex:
        capex_panel_graph(df, fin_general)
    if fin_panel.enable_opex:
        opex_panel_graph(df, fin_general)

def capex_panel_graph(df, fin_general):

    capex_bar_graph(
        df=df,
        capex_keys=[
            "Total Panel Price",
            "Total Installation Price",
            "Total Cable Price",
            "Total Cable Installation Price"
        ],
        label_map_grouped={
            "Panel\n(Device + Installation)": [
                "Total Panel Price",
                "Total Installation Price"
            ],
            "Cables\n(Acquisition + Installation)": [
                "Total Cable Price",
                "Total Cable Installation Price"
            ]
        },
        colors=['#969696', '#636363'],
        title='Capex components – Panel-based system',
        currency_symbol=fin_general.currency_symbol,
        filename=f"{fin_general.save_report_path}/panel_capex_components.png",
        total_box_edgecolor='gray'
    )
        
        
def opex_panel_graph(df, fin_general):

    opex_pie_graph(
        df=df,
        opex_keys=[
            "Annual Maintenance Price",
            "Annual Energy Price"
        ],
        label_map={
            "Annual Maintenance Price": "Panel\nMaintenance",
            "Annual Energy Price": "Panel\nEnergy"
        },
        color_map={
            "Panel\nMaintenance": "#bdbdbd",
            "Panel\nEnergy": "#636363"
        },
        title="Opex components – Panel-based system",
        currency_symbol=fin_general.currency_symbol,
        filename=f"{fin_general.save_report_path}/panel_opex_components.png",
        total_box_edgecolor="#636363"
    )


#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------Funções Auxiliares-----------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def calculate_panels_location(p, df):
    p_fields = p.simulation.devices.panel.database.fields

    centroids = df.groupby(p_fields.panel_num).agg(
        Lat_Panel=(p_fields.lat, "mean"),
        Long_Panel=(p_fields.lon, "mean")
    ).reset_index()

    return centroids



# Main function that uses MST per branch and panel
def calculate_cables_size(df_panels, df_panels_locations, p):

    p_fields = p.simulation.devices.panel.database.fields

    grouped_by_panel = df_panels.groupby(p_fields.panel_num)
    meters_by_panel = []

    for panel, panel_group in grouped_by_panel:

        # Get panel location
        panel_row = df_panels_locations[df_panels_locations[p_fields.panel_num] == panel].iloc[0]
        panel_lat = panel_row['Lat_Panel']
        panel_lon = panel_row['Long_Panel']

        branch_sums = []

        for branch in panel_group[p_fields.branch_num].unique():

            branch_group = panel_group[panel_group[p_fields.branch_num] == branch].copy()

            # Create a list of nodes: include the panel and all points in the branch
            nodes = ['PANEL'] + list(branch_group.index)

            # Create a dictionary with the locations
            locations = {'PANEL': (panel_lat, panel_lon)}
            for idx, row in branch_group.iterrows():
                locations[idx] = (row[p_fields.lat], row[p_fields.lon])

            # Calculate all possible edges
            edges = []
            for (n1, n2) in combinations(nodes, 2):
                lat1, lon1 = locations[n1]
                lat2, lon2 = locations[n2]
                d = haversine(lat1, lon1, lat2, lon2)
                edges.append((d, n1, n2))

            # Sort the edges by smallest distance
            edges.sort()

            # Apply Kruskal's algorithm
            uf = UnionFind(nodes)
            mst_weight = 0

            for d, n1, n2 in edges:
                if uf.union(n1, n2):
                    mst_weight += d

            branch_sums.append(mst_weight)

        panel_sum = sum(branch_sums)
        meters_by_panel.append(panel_sum)

    total_cables_size = sum(meters_by_panel)

    return total_cables_size


# Function to calculate the distance between two geographical points (Haversine formula)
def haversine(lat1, lon1, lat2, lon2):
    
    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    # Differences between the points
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Haversine formula
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    # Radius of Earth in meters
    r = 6371 * 1000 

    return c * r


# Union-Find class for Kruskal's algorithm
class UnionFind:
    def __init__(self, elements):
        self.parent = {e: e for e in elements}

    def find(self, e):
        if self.parent[e] != e:
            self.parent[e] = self.find(self.parent[e])
        return self.parent[e]

    def union(self, e1, e2):
        root1 = self.find(e1)
        root2 = self.find(e2)
        if root1 != root2:
            self.parent[root2] = root1
            return True
        return False