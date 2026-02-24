import numpy as np
import folium
from folium.plugins import MarkerCluster
from folium import Element
import debugpy
#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------- Clustering Remaining Points into Edge/Fog Groups -----------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

def create_edges_fogs(p, points_table, used_percentage):

    p_fields = p.simulation.devices.edge_fog.database.fields
    p_clustering = p.clustering.devices.edge_fog
    percentage_edge = p_clustering.percentage

    # Organize points by cell
    df_organized = points_table.sort_values(
        by=[p_fields.lat_cell, p_fields.lon_cell],
        ascending=[False, False]
    ).copy()

    # Create 'Cell' column identifying each unique (lat_cell, lon_cell)
    df_organized["cell_num"] = (
        df_organized.groupby([p_fields.lat_cell, p_fields.lon_cell]).ngroup() + 1
    )

    # Initialize fog/edge fields
    df_organized[p_fields.fog_num] = None
    df_organized[p_fields.edge_num] = None
    df_organized[p_fields.is_fog] = False

    if used_percentage == 1:
        return points_table, None
    total_points = int(points_table.shape[0] / (1 - used_percentage))
    
    if percentage_edge + used_percentage == 1:
        max_points = total_points - 1 
    else:
        max_points = round(total_points * percentage_edge) - 1
    count_points = 0
        

    fog_number = 1
    max_cells = df_organized["cell_num"].max()

    cell = 1
    while cell <= max_cells:
        
        if count_points > max_points:
            break

        return_to_begin = False

        # Select all points in the current cell
        cell_points = df_organized[df_organized["cell_num"] == cell].copy()

        # Remove points already assigned to fog
        cell_points = cell_points[cell_points[p_fields.fog_num].isnull()]

        if cell_points.empty:
            cell += 1
            continue

        # Determine the origin of this cell
        lat_cell_origin = cell_points[p_fields.lat_cell].iloc[0]
        lon_cell_origin = cell_points[p_fields.lon_cell].iloc[0]

        # Convert origin to km
        lat_origin_km = lat_cell_origin * p_clustering.max_range_km
        lon_origin_km = lon_cell_origin * p_clustering.max_range_km

        # Convert latitude/longitude of points to kilometers
        cell_points["Lat_km"] = cell_points[p_fields.lat] * 111
        cell_points["Lon_km"] = cell_points[p_fields.lon] * (
            111 * np.cos(np.deg2rad(cell_points[p_fields.lat]))
        )

        # Euclidean distance to origin
        cell_points["Distance_to_origin"] = np.sqrt(
            (cell_points["Lat_km"] - lat_origin_km)**2 +
            (cell_points["Lon_km"] - lon_origin_km)**2
        )

        # The closest point becomes the reference
        closest_point = cell_points.loc[cell_points["Distance_to_origin"].idxmin()]

        vector_cluster = []
        count_points_edge = 0

        # Neighbor clusters to search
        neighbor_clusters = [(0,0),(1,0),(0,1),(1,1)]

        # Outer cluster loop
        for ind_cluster_1, (adj_lat, adj_lon) in enumerate(neighbor_clusters):

            # Select points for (0,0) or neighbors
            if (adj_lat, adj_lon) == (0,0):
                cell_points = cell_points.drop(columns=["Distance_to_origin"])
            else:
                lat_neighbor = lat_cell_origin + adj_lat
                lon_neighbor = lon_cell_origin + adj_lon

                cell_points = df_organized[
                    (df_organized[p_fields.lat_cell] == lat_neighbor) &
                    (df_organized[p_fields.lon_cell] == lon_neighbor)
                ].copy()

                cell_points = cell_points[cell_points[p_fields.fog_num].isnull()]

                cell_points["Lat_km"] = cell_points[p_fields.lat] * 111
                cell_points["Lon_km"] = cell_points[p_fields.lon] * (
                    111 * np.cos(np.deg2rad(cell_points[p_fields.lat]))
                )

            # Distance to the reference point
            cell_points["Distance_to_closest_point"] = np.sqrt(
                (cell_points["Lat_km"] - closest_point["Lat_km"])**2 +
                (cell_points["Lon_km"] - closest_point["Lon_km"])**2
            )

            cell_points_sorted = cell_points.sort_values(
                by="Distance_to_closest_point", ascending=True
            )

            # Iterate through sorted points
            for idx, (_, point) in enumerate(cell_points_sorted.iterrows()):

                if count_points_edge < p_clustering.max_points:

                    if point["Distance_to_closest_point"] <= p_clustering.max_range_km:

                        point = point.drop(labels=["Distance_to_closest_point"])
                        vector_cluster.append(point)
                        count_points_edge += 1

                    else:
                        fog_point = cell_points_sorted.iloc[idx-1]

                        # SECOND LEVEL NEIGHBOR SCAN
                        for ind_cluster_2, (adj_lat_2, adj_lon_2) in enumerate(neighbor_clusters):

                            if (adj_lat_2, adj_lon_2) == (0,0):
                                cell_points = cell_points.drop(columns=["Distance_to_closest_point"])

                                ids_in_cluster = [pt[p_fields.id] for pt in vector_cluster]
                                cell_points = cell_points[~cell_points[p_fields.id].isin(ids_in_cluster)]

                            else:
                                lat_new = lat_cell_origin + adj_lat_2
                                lon_new = lon_cell_origin + adj_lon_2

                                cell_points = df_organized[
                                    (df_organized[p_fields.lat_cell] == lat_new) &
                                    (df_organized[p_fields.lon_cell] == lon_new)
                                ].copy()

                                cell_points = cell_points[cell_points[p_fields.fog_num].isnull()]

                                ids_in_cluster = [pt[p_fields.id] for pt in vector_cluster]
                                cell_points = cell_points[~cell_points[p_fields.id].isin(ids_in_cluster)]

                                cell_points["Lat_km"] = cell_points[p_fields.lat] * 111
                                cell_points["Lon_km"] = cell_points[p_fields.lon] * (
                                    111 * np.cos(np.deg2rad(cell_points[p_fields.lat]))
                                )

                            # distance to fog_point
                            cell_points["Distance_to_fog_point"] = np.sqrt(
                                (cell_points["Lat_km"] - fog_point["Lat_km"])**2 +
                                (cell_points["Lon_km"] - fog_point["Lon_km"])**2
                            )

                            cell_points_sorted = cell_points.sort_values(
                                by="Distance_to_fog_point", ascending=True
                            )

                            # iterate points again
                            for idx2, (_, point2) in enumerate(cell_points_sorted.iterrows()):

                                if count_points_edge < p_clustering.max_points:

                                    if point2["Distance_to_fog_point"] <= p_clustering.max_range_km:
                                        point2 = point2.drop(labels=["Distance_to_fog_point"])
                                        vector_cluster.append(point2)
                                        count_points_edge += 1

                                    else:
                                        if ind_cluster_2 == 3:
                                            df_organized, fog_number = find_best_point_and_update_edge_fog(
                                                p, df_organized, vector_cluster, fog_number,
                                                findbest=False, fog_point=fog_point
                                            )
                                            return_to_begin = True
                                        break

                                else:
                                    df_organized, fog_number = find_best_point_and_update_edge_fog(
                                        p, df_organized, vector_cluster, fog_number,
                                        findbest=True, check_distance=True,
                                        fog_point=fog_point,
                                        max_range_edge_km=p_clustering.max_range_km
                                    )
                                    return_to_begin = True

                                if return_to_begin:
                                    break

                            if ind_cluster_2 == 3 and not return_to_begin:
                                df_organized, fog_number = find_best_point_and_update_edge_fog(
                                    p, df_organized, vector_cluster, fog_number,
                                    findbest=True, check_distance=True,
                                    fog_point=fog_point,
                                    max_range_edge_km=p_clustering.max_range_km
                                )
                                return_to_begin = True

                            if return_to_begin:
                                break

                else:
                    df_organized, fog_number = find_best_point_and_update_edge_fog(
                        p, df_organized, vector_cluster, fog_number,
                        findbest=True, check_distance=False
                    )
                    return_to_begin = True

                if return_to_begin:
                    break

            if ind_cluster_1 == 3 and not return_to_begin:
                df_organized, fog_number = find_best_point_and_update_edge_fog(
                    p, df_organized, vector_cluster, fog_number,
                    findbest=True, check_distance=False
                )
                return_to_begin = True

            if return_to_begin:
                break

        count_points = df_organized[p_fields.fog_num].notnull().sum()

        cell += 1

    # Build dynamic edge-fog names
    p_fields_f = p.simulation.devices.edge_fog.database.fields
    df_organized[p_fields_f.name] = df_organized.apply(
        lambda row: f"Edge{row[p_fields_f.edge_num]}_Fog{row[p_fields_f.fog_num]}_{int(row[p_fields_f.is_fog])}",
        axis=1
    )
        
    df_organized = df_organized.sort_values(
        by=[p_fields_f.fog_num, p_fields_f.edge_num]
    )
    
    df_edges = create_edges_fog_ids(p, df_organized)
    df_edges.drop(columns=["cell_num"], inplace=True)
    df_edges = df_edges.reset_index(drop=True)

    fogs_created = int(df_edges[p_fields.is_fog].sum())
    total_assigned = int(len(df_edges))
    print(
        f"Fogs created: {fogs_created}"
        f"\n Streetlights assigned to edge_fog: {total_assigned}\n"
    )
    
    return points_table, df_edges
 

def find_best_point_and_update_edge_fog(
    p, df, vector_cluster, fog_number,
    findbest=True, check_distance=False,
    fog_point=None, max_range_edge_km=9999
):
    p_fields = p.simulation.devices.edge_fog.database.fields

    if findbest:
        # Select the best fog point by minimal variance
        lat_km = np.array([pt["Lat_km"] for pt in vector_cluster])
        lon_km = np.array([pt["Lon_km"] for pt in vector_cluster])

        avg_lat_km = lat_km.mean()
        avg_lon_km = lon_km.mean()

        distances_to_avg = np.sqrt(
            (lat_km - avg_lat_km)**2 + (lon_km - avg_lon_km)**2
        )

        best_point = vector_cluster[np.argmin(distances_to_avg)]

        if check_distance:
            distances = np.sqrt(
                (lat_km - best_point["Lat_km"])**2 +
                (lon_km - best_point["Lon_km"])**2
            )
            if distances.max() <= max_range_edge_km:
                fog_point = best_point
        else:
            fog_point = best_point

    # Update dataframe with fog assignment
    df.loc[fog_point.name, p_fields.is_fog] = True

    indices = [pt.name for pt in vector_cluster]
    df.loc[indices, p_fields.fog_num] = fog_number
    df.loc[indices, p_fields.edge_num] = range(1, len(indices) + 1)
    fog_number += 1

    return df, fog_number


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
#--------------------------------------------------------- Create Variants of Base IDs for Edges -----------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

def generate_variant_id(base_id):
    """
    Generates a small variation of the given base ID.
    Example:
        base: "AA:BB:CC:DD:EE:FF"
        new:  "AA:BB:CC:DD:EE:XY"
    """

    parts = base_id.split(":")
    new_last_byte = ''.join(random.choices('0123456789ABCDEF', k=2))
    parts[-1] = new_last_byte
    return ":".join(parts)



#----------------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------- Assign Edge/Fog IDs (E_ID, F_ID) --------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------------------------------------------------------------

def create_edges_fog_ids(p, df):
    """
    Assigns:
        - one F_ID per fog
        - one E_ID per edge
    Fog points receive the same E_ID = F_ID
    Edge points receive a variation of the fog's base ID
    """

    p_fields = p.simulation.devices.edge_fog.database.fields

    fog_num_col = p_fields.fog_num
    is_fog_col = p_fields.is_fog
    fog_id_col = p_fields.fog_id
    edge_id_col = p_fields.edge_id

    # Generate base ID per fog
    fog_to_base_id = {
        fog: generate_base_id()
        for fog in df[fog_num_col].unique()
    }

    # Assign F_ID
    df[fog_id_col] = df[fog_num_col].apply(lambda fog: fog_to_base_id[fog])

    # Assign E_ID based on Fog/Edge classification
    df[edge_id_col] = df.apply(
        lambda row: (
            row[fog_id_col] if row[is_fog_col]
            else generate_variant_id(row[fog_id_col])
        ),
        axis=1
    )

    return df


def add_marker_edge_fog(p, df_device, marker_cluster, icon_colors):
    
    
    p_edge_fog = p.clustering.devices.edge_fog
    fields = p.simulation.devices.edge_fog.database.fields
    # add lighting points to the cluster map
    for idx, row in df_device.iterrows():
        popup_parts = []
        for _, value in p_edge_fog.labels.items():
            label = getattr(fields,value)
            if label in row:
                popup_parts.append(f"{label}: {row[label]}")
            else:
                print(f"[WARN] Missing label column '{label}' in edge_fog dataframe; skipping.")
        popup_text = ", ".join(popup_parts)
          
        icon = icon_colors[1] if row[fields.is_fog] else icon_colors[0]             
        folium.Marker(
            location=[row[fields.lat], row[fields.lon]],
            popup=popup_text,
            icon=folium.Icon(color=icon)
        ).add_to(marker_cluster)
