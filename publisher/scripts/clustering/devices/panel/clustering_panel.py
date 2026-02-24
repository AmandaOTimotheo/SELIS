import folium
from folium.plugins import MarkerCluster
from folium import Element
import debugpy
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------ Create Panels Based on Density --------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

def create_panels(p, points_table, used_percentage):

    # Extract field dict
    p_fields = p.simulation.devices.panel.database.fields
    
    # Compute densities
    density_table = (
        points_table
        .groupby([p_fields.lat_cell, p_fields.lon_cell])
        .size()
        .reset_index(name="Density")
    ).copy()

    # Add cluster name also in density table
    density_table[p_fields.cluster_name] = (
        density_table[p_fields.lat_cell].astype(str) + "_" +
        density_table[p_fields.lon_cell].astype(str)
    )
    
    panel_cfg = p.clustering.devices.panel
    n_branchs = panel_cfg.n_branchs
    min_points_branch = panel_cfg.min_points_branch
    max_points_branch = panel_cfg.max_points_branch
    percentage_panel = panel_cfg.percentage

    # Panel index counter
    panel_index = 1

    
    # Use the already-renamed panel id column
    id_col = p_fields.id

    # Create Panel and Branch columns
    points_table[[p_fields.panel_num, p_fields.branch_num]] = None

    if used_percentage == 1:
        return points_table, None
    total_points = int(points_table.shape[0] / (1 - used_percentage))
    
    if percentage_panel + used_percentage == 1:
        max_points = total_points
    else:
        max_points = round(total_points * percentage_panel)
    count_points = 1
        
    # Sort density: highest first
    density_table_sorted = density_table.sort_values(by="Density", ascending=False).copy()

    # Iterate over clusters by density
    for _, cluster in density_table_sorted.iterrows():

        if count_points > max_points:
            break
        
        current_density = cluster["Density"]
        cluster_lat = cluster[p_fields.lat_cell]
        cluster_lon = cluster[p_fields.lon_cell]

        count_points += current_density

        # Select all points from this cluster
        selected_points = points_table[
            (points_table[p_fields.lat_cell] == cluster_lat) &
            (points_table[p_fields.lon_cell] == cluster_lon)
        ].copy()

        irow = 0

        # Determine panel sizes
        min_points_panel = min_points_branch * n_branchs
        max_points_panel = max_points_branch * n_branchs
        n_panels = find_n_for_density_range(current_density, min_points_panel, max_points_panel)

        # Small densities may not fit constraints; fallback to a single panel
        if not n_panels:
            n_panels = 1

        panels_size = define_groups_size(current_density, n_panels, min_points_panel, max_points_panel)

        # Use the actual computed panel sizes length to avoid out-of-range
        for j_panel in range(len(panels_size)):

            panel_points = panels_size[j_panel]

            branch_index = 1
            branchs_size = define_groups_size(panel_points, n_branchs, min_points_branch, max_points_branch)

            # Use actual branchs_size length to prevent index errors
            for j_branch in range(len(branchs_size)):
                branch_points = branchs_size[j_branch]

                for _ in range(branch_points):
                    if irow >= len(selected_points):
                        break
                    selected_id = selected_points.iloc[irow][id_col]
                    points_table.loc[
                        (points_table[p_fields.id] == selected_id),
                        [p_fields.panel_num, p_fields.branch_num]
                    ] = [panel_index, branch_index]
                    irow += 1

                branch_index += 1

            panel_index += 1



    # Panel name based on panel_num
    points_table[p_fields.name] = points_table[p_fields.panel_num].apply(
        lambda x: f"Panel_{x}"
    )
    
    
    # Filter only panel points and sort
    df_device = filter_panels(p, points_table).copy()
    # Sort using field attributes
    df_device = df_device.sort_values(by=[p_fields.panel_num, p_fields.branch_num])
    
    # Assign unique IDs and calculate average panel location
    df_device = create_panels_ids(p, df_device)
    
    # Remove_panels from original table
    points_table = remove_panels(p, points_table) 

    panels_created = int(df_device[p_fields.panel_num].nunique()) if not df_device.empty else 0
    luminarias_assigned = int(len(df_device))
    print(
        f"Panels created: {panels_created}"
        f"\n Streetlights assigned to panel: {luminarias_assigned}\n"
    ) 

    
    return points_table, df_device


#-----------------------------------------------------------------------------------------------------------------------------------------------------------------
#-------------------------------------------------------- Calculate Panel Centroids -------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

def calculate_panels_location(p, df):
    p_fields = p.simulation.devices.panel.database.fields

    centroids = df.groupby(p_fields.panel_num).agg(
        Lat_Panel=(p_fields.lat, "mean"),
        Long_Panel=(p_fields.lon, "mean")
    ).reset_index()

    return centroids

#-----------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------- Filter Panels -----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

def filter_panels(p, df):
    panel_num = p.simulation.devices.panel.database.fields.panel_num
    df = df.drop(df[df[panel_num].isna()].index)
    return df


#-----------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------- Remove Panels -----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

def remove_panels(p, df):
    p_fields = p.simulation.devices.panel.database.fields

    panel_num = p_fields.panel_num
    branch_num = p_fields.branch_num

    # Remove rows that HAVE panel assigned
    df = df.drop(df[~df[panel_num].isna()].index)

    # Drop panel-related columns
    df = df.drop(columns=[panel_num, branch_num])

    return df


#-----------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------- Define Points per Branch --------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

def define_groups_size(total_size, n_groups, min_points, max_points):
    """
    Divides total points into 'n_groups' such that:
     - Each group has between min_points and max_points
     - The total sum matches exactly total_size
    """

    # Fallbacks for small/invalid scenarios to avoid infinite loops
    if total_size <= 0:
        return [0]

    if not n_groups or n_groups <= 0:
        return [int(total_size)]

    # If constraints cannot be met (too few points), collapse into a single group
    if total_size < n_groups * min_points:
        return [int(total_size)]

    # Base even split using floor + remainder (prevents overshoot from rounding)
    base = total_size // n_groups
    remainder = total_size % n_groups
    groups = [base + (1 if i < remainder else 0) for i in range(n_groups)]

    # Clamp to min/max
    groups = [max(min_points, min(max_points, g)) for g in groups]

    # Adjust difference with a bounded number of iterations to prevent infinite loops
    difference = total_size - sum(groups)
    for _ in range(100):
        if difference == 0:
            break

        for i in range(n_groups):
            if difference == 0:
                break

            if difference > 0 and groups[i] < max_points:
                increment = min(difference, max_points - groups[i])
                groups[i] += increment
                difference -= increment

            elif difference < 0 and groups[i] > min_points:
                decrement = min(-difference, groups[i] - min_points)
                groups[i] -= decrement
                difference += decrement

    # If still not balanced due to tight constraints, dump the residual into the first group
    if difference != 0:
        groups[0] = max(min_points, min(max_points, groups[0] + difference))

    return groups



#-----------------------------------------------------------------------------------------------------------------------------------------------------------------
#-------------------------------------------------------- Panel Count for Density Ranges -------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------

def find_n_for_density_range(current_density, initial_range, final_range):
    """
    Given a density value "current_density", find the number of panels n such that:
        initial_range <= (current_density / n) <= final_range
    Returns:
        n or None
    """
    for n in range(1, int(current_density) + 1):
        result = current_density / n
        if initial_range <= result <= final_range:
            return n
    return None



#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------- Assign Panel IDs ("P_ID") -------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

def create_panels_ids(p, df):
    """
    Assigns a unique base ID to each panel.
    Column added: p_fields["panel_id"]
    """

    p_fields = p.simulation.devices.panel.database.fields

    panel_num_col = p_fields.panel_num
    panel_id_col = p_fields.panel_id

    # Map: panel_number → generated base ID
    panel_to_id = {
        panel: generate_base_id()
        for panel in df[panel_num_col].unique()
    }

    # Assign mapping
    df[panel_id_col] = df[panel_num_col].apply(lambda panel: panel_to_id[panel])

    return df


#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------ Generate Unique IDs ("XX:XX:XX:XX:XX:XX") ---------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

import random


def generate_base_id():
    """
    Generates a 6-byte hexadecimal ID in the form:
        "AA:BB:CC:DD:EE:FF"
    """
    base_id = ''.join(random.choices('0123456789ABCDEF', k=2))
    for _ in range(5):
        base_id += ":" + ''.join(random.choices('0123456789ABCDEF', k=2))
    return base_id


#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------ Add Markers to Map --------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

def add_marker_panel(p, df_device, marker_cluster, icon_colors):
    
    df_panels_locations = calculate_panels_location(p, df_device)
    
    p_panel = p.clustering.devices.panel
    fields = p.simulation.devices.panel.database.fields
    # add lighting points to the cluster map
    for idx, row in df_device.iterrows():
        popup_parts = []
        for _, value in p_panel.labels.items():
            label = getattr(fields,value)
            if label in row:
                popup_parts.append(f"{label}: {row[label]}")
            else:
                print(f"[WARN] Missing label column '{label}' in panel dataframe; skipping.")
        popup_text = ", ".join(popup_parts)
             
        folium.Marker(
            location=[row[fields.lat], row[fields.lon]],
            popup=popup_text,
            icon=folium.Icon(color=icon_colors[0])
        ).add_to(marker_cluster)
    
    # Add panel locations to the cluster map
    for idx, row in df_panels_locations.iterrows():
        folium.Marker(
            location=[row["Lat_Panel"], row["Long_Panel"]],
            popup=f"{fields.panel_num}: {row[fields.panel_num]}",
            icon=folium.Icon(color=icon_colors[1])
        ).add_to(marker_cluster)