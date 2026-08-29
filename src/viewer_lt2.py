import pandas as pd
import matplotlib.pyplot as plt

# ------------------------------------------------------------
# Cargar datos
# ------------------------------------------------------------

levels = pd.read_csv("data/geometry/levels.csv")
grid_x = pd.read_csv("data/geometry/grid_x.csv")
grid_y = pd.read_csv("data/geometry/grid_y.csv")
vertical = pd.read_csv("data/geometry/vertical_elements_LT2.csv")
walls = pd.read_csv("data/geometry/walls_LT2.csv")


# Diccionarios eje -> coordenada
x_axis = dict(zip(grid_x["axis_id"].astype(str), grid_x["x_m"]))
y_axis = dict(zip(grid_y["axis_id"].astype(str), grid_y["y_m"]))
z_level = dict(zip(levels["name"].astype(str), levels["z_m"]))


# ------------------------------------------------------------
# Figura 3D
# ------------------------------------------------------------

fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection="3d")


# ------------------------------------------------------------
# Dibujar columnas
# ------------------------------------------------------------

columns = vertical[vertical["type"] == "column"]

for _, col in columns.iterrows():

    axis_x = str(col["axis_x"])
    axis_y = str(col["axis_y"])

    if axis_x not in x_axis or axis_y not in y_axis:
        print(
            f"WARNING: {col['element_id']} "
            f"references undefined axis {axis_x}-{axis_y}"
        )
        continue

    x = x_axis[axis_x]
    y = y_axis[axis_y]

    z1 = z_level[col["from_level"]]
    z2 = z_level[col["to_level"]]

    ax.plot(
        [x, x],
        [y, y],
        [z1, z2],
        linewidth=3
    )

    # ID
    ax.text(
        x,
        y,
        z2,
        str(col["element_id"]),
        fontsize=7
    )


# ------------------------------------------------------------
# Dibujar muros
# ------------------------------------------------------------

if len(walls) > 0:

    for _, wall in walls.iterrows():

        z1 = z_level[wall["from_level"]]
        z2 = z_level[wall["to_level"]]

        # línea inferior
        ax.plot(
            [wall["x1_m"], wall["x2_m"]],
            [wall["y1_m"], wall["y2_m"]],
            [z1, z1],
            linewidth=4
        )

        # línea superior
        ax.plot(
            [wall["x1_m"], wall["x2_m"]],
            [wall["y1_m"], wall["y2_m"]],
            [z2, z2],
            linewidth=4
        )

        # extremos verticales
        ax.plot(
            [wall["x1_m"], wall["x1_m"]],
            [wall["y1_m"], wall["y1_m"]],
            [z1, z2],
            linewidth=2
        )

        ax.plot(
            [wall["x2_m"], wall["x2_m"]],
            [wall["y2_m"], wall["y2_m"]],
            [z1, z2],
            linewidth=2
        )


# ------------------------------------------------------------
# Mostrar niveles
# ------------------------------------------------------------

xmin = grid_x["x_m"].min()
xmax = grid_x["x_m"].max()
ymin = grid_y["y_m"].min()
ymax = grid_y["y_m"].max()

for _, level in levels.iterrows():

    z = level["z_m"]

    ax.plot(
        [xmin, xmax],
        [ymin, ymin],
        [z, z],
        linewidth=0.5
    )

    ax.text(
        xmin,
        ymin,
        z,
        f"  {level['name']} ({z:.2f} m)",
        fontsize=7
    )


# ------------------------------------------------------------
# Configuración
# ------------------------------------------------------------

ax.set_xlabel("X [m]")
ax.set_ylabel("Y [m]")
ax.set_zlabel("Z [m]")

ax.set_title("LT2 - Viewer geométrico preliminar")

ax.set_box_aspect([
    xmax - xmin,
    ymax - ymin,
    levels["z_m"].max() - levels["z_m"].min()
])

plt.tight_layout()

plt.savefig(
    "figures/lt2_geometry_preview.png",
    dpi=200
)

plt.show()