from capex_opex_analysis.financial_report_graphs import *
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#-------------------------------------------------------------------------------------Edge_Fog-------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Selected the choosed technology - LoRa or GPRS

def edge_fog_capex_opex_report(df_edges, p):
    
    fin_general = p.financial.general
    fin_edge = p.financial.devices.edge_fog
    comm = fin_edge.active_communication
   
    n_fogs = int(df_edges['isFog'].sum())
    n_edges = int((df_edges['isFog'] == False).sum())

    # CAPEX (Capital Expediture) ------------------------------------------------------------------
    total_fogs_price = n_fogs * comm.price_per_fog
    total_fogs_installation_price = n_fogs * comm.price_fog_installation
    total_edges_price = n_edges * comm.price_per_edge
    total_edges_installation_price = n_edges * comm.price_edge_installation
    total_price = total_fogs_price + total_fogs_installation_price + total_edges_price + total_edges_installation_price

    # OPEX (Operational Expediture) -----------------------------------------------------------------
    fogs_annual_maintenance_price = n_fogs * comm.price_fog_annual_maintenance
    edges_annual_maintenance_price = n_edges * comm.price_edge_annual_maintenance
    total_annual_maintenance = fogs_annual_maintenance_price + edges_annual_maintenance_price

    annual_fog_energy_price = n_fogs * (24 * 365) * (comm.fog_power_W / 1000) * fin_general.price_kWh
    annual_edge_energy_price = n_edges * (24 * 365) * (comm.edge_power_W / 1000) * fin_general.price_kWh
    total_annual_energy_price = annual_fog_energy_price + annual_edge_energy_price

    opex_annual_cost = total_annual_maintenance + total_annual_energy_price

    #----------------------------------------------------------------------------------------------
    # Organize data into a dictionary
    
    data_output = {
        "Number of Fogs": [n_fogs],
        "Number of Edges": [n_edges],
        "Total Fogs Price": [total_fogs_price],
        "Total Fogs Installation Price": [total_fogs_installation_price],
        "Total Edges Price": [total_edges_price],
        "Total Edges Installation Price": [total_edges_installation_price],
        "Total Investment Price": [total_price],
        "Annual Fogs Maintenance Price": [fogs_annual_maintenance_price],
        "Annual Edges Maintenance Price": [edges_annual_maintenance_price],
        "Total Annual Maintenance Price": [total_annual_maintenance],
        "Annual Fog Energy Price": [annual_fog_energy_price],
        "Annual Edge Energy Price": [annual_edge_energy_price],
        "Total Annual Energy Price": [total_annual_energy_price],
        "Total Annual Opex Cost": [opex_annual_cost]
    }

    data_output = pd.DataFrame(data_output)
    # Transpose the DataFrame
    data_output_transposed = pd.DataFrame({"Variables": data_output.columns,"Values": data_output.iloc[0]})
    data_output_transposed["Values"] = data_output_transposed["Values"].round()
    data_output_transposed.to_csv(f"{fin_general.save_report_path}/edge_fog_financial_report.csv", index=False)

    edge_fog_graphs(data_output_transposed, p)
    
    print(f"Edge/Fog financial report saved to {fin_general.save_report_path}/edge_fog_financial_report.csv")

    return  data_output_transposed




def edge_fog_graphs(df, p):
    fin_general = p.financial.general
    fin_edge = p.financial.devices.edge_fog

    if fin_edge.enable_capex:
        capex_edge_graph(df, fin_general)
    if fin_edge.enable_opex:
        opex_edge_fog_graph(df, fin_general)
    
    
def capex_edge_graph(df, fin_general):

    capex_bar_graph(
        df=df,
        capex_keys=[
            "Total Edges Price",
            "Total Edges Installation Price",
            "Total Fogs Price",
            "Total Fogs Installation Price"
        ],
        label_map_grouped={
            "Edge\n(Device + Installation)": [
                "Total Edges Price",
                "Total Edges Installation Price"
            ],
            "Fog\n(Device + Installation)": [
                "Total Fogs Price",
                "Total Fogs Installation Price"
            ]
        },
        colors=['#2171b5', '#6baed6'],
        title='Capex components – Edge/Fog-based system',
        currency_symbol=fin_general.currency_symbol,
        filename=f"{fin_general.save_report_path}/edge_fog_capex_components.png",
        total_box_edgecolor='lightblue'
    )




def opex_edge_fog_graph(df, fin_general):

    opex_pie_graph(
        df=df,
        opex_keys=[
            "Annual Fogs Maintenance Price",
            "Annual Edges Maintenance Price",
            "Annual Fog Energy Price",
            "Annual Edge Energy Price"
        ],
        label_map={
            "Annual Fogs Maintenance Price": "Fog\nMaintenance",
            "Annual Edges Maintenance Price": "Edge\nMaintenance",
            "Annual Fog Energy Price": "Fog\nEnergy",
            "Annual Edge Energy Price": "Edge\nEnergy"
        },
        color_map={
            "Edge\nMaintenance": "#2171b5",
            "Edge\nEnergy": "#6baed6",
            "Fog\nMaintenance": "#9ecae1",
            "Fog\nEnergy": "#c6dbef"
        },
        title="Opex components – Edge/Fog-based system",
        currency_symbol=fin_general.currency_symbol,
        filename=f"{fin_general.save_report_path}/edge_fog_opex_components.png",
        total_box_edgecolor="#2171b5"
    )
