import sqlite3
from datetime import datetime

DB_NAME = "inventario.db"


def conectar():
    conexion = sqlite3.connect(DB_NAME)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_tablas():
    with conectar() as conexion:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                precio REAL NOT NULL CHECK(precio >= 0),
                cantidad INTEGER NOT NULL CHECK(cantidad >= 0)
            )
        """)

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                cantidad INTEGER NOT NULL CHECK(cantidad > 0),
                fecha TEXT NOT NULL,
                FOREIGN KEY (producto_id)
                    REFERENCES productos(id)
                    ON DELETE RESTRICT
            )
        """)


def leer_entero(mensaje, minimo=None):
    while True:
        try:
            valor = int(input(mensaje))
            if minimo is not None and valor < minimo:
                print(f"El valor debe ser como minimo {minimo}.")
                continue
            return valor
        except ValueError:
            print("Debes ingresar un numero entero valido.")


def leer_precio(mensaje):
    while True:
        try:
            valor = float(input(mensaje).replace(",", "."))
            if valor < 0:
                print("El precio no puede ser negativo.")
                continue
            return valor
        except ValueError:
            print("Ingresa un precio valido.")


def registrar_producto():
    nombre = input("Nombre del producto: ").strip()

    if not nombre:
        print("El nombre no puede estar vacio.")
        return

    precio = leer_precio("Precio: ")
    cantidad = leer_entero("Cantidad disponible: ", 0)

    try:
        with conectar() as conexion:
            conexion.execute(
                """INSERT INTO productos (nombre, precio, cantidad)
                   VALUES (?, ?, ?)""",
                (nombre, precio, cantidad)
            )
        print("Producto registrado correctamente.")
    except sqlite3.IntegrityError as error:
        print("No se pudo registrar el producto:", error)


def consultar_productos():
    with conectar() as conexion:
        productos = conexion.execute(
            """SELECT id, nombre, precio, cantidad
               FROM productos ORDER BY id"""
        ).fetchall()

    if not productos:
        print("No hay productos registrados.")
        return

    print("\n--- INVENTARIO ---")
    print(f"{'ID':<5}{'NOMBRE':<25}{'PRECIO':<15}{'CANTIDAD':<10}")
    for producto in productos:
        print(
            f"{producto[0]:<5}{producto[1]:<25}"
            f"${producto[2]:<14.2f}{producto[3]:<10}"
        )


def actualizar_producto():
    consultar_productos()
    producto_id = leer_entero("ID del producto a actualizar: ", 1)

    with conectar() as conexion:
        producto = conexion.execute(
            "SELECT id FROM productos WHERE id = ?",
            (producto_id,)
        ).fetchone()

    if producto is None:
        print("El producto no existe.")
        return

    print("1. Actualizar precio")
    print("2. Actualizar cantidad")
    print("3. Actualizar ambos")
    opcion = input("Selecciona una opcion: ")

    try:
        with conectar() as conexion:
            if opcion in ("1", "3"):
                precio = leer_precio("Nuevo precio: ")
                conexion.execute(
                    "UPDATE productos SET precio = ? WHERE id = ?",
                    (precio, producto_id)
                )

            if opcion in ("2", "3"):
                cantidad = leer_entero("Nueva cantidad: ", 0)
                conexion.execute(
                    "UPDATE productos SET cantidad = ? WHERE id = ?",
                    (cantidad, producto_id)
                )

            if opcion not in ("1", "2", "3"):
                print("Opcion no valida.")
                return

        print("Producto actualizado correctamente.")
    except sqlite3.Error as error:
        print("Error al actualizar:", error)


def eliminar_producto():
    consultar_productos()
    producto_id = leer_entero("ID del producto a eliminar: ", 1)

    try:
        with conectar() as conexion:
            cursor = conexion.execute(
                "DELETE FROM productos WHERE id = ?",
                (producto_id,)
            )

            if cursor.rowcount == 0:
                print("El producto no existe.")
            else:
                print("Producto eliminado correctamente.")
    except sqlite3.IntegrityError:
        print(
            "No se puede eliminar: el producto tiene ventas "
            "relacionadas en el historial."
        )


def registrar_venta():
    consultar_productos()
    producto_id = leer_entero("ID del producto vendido: ", 1)
    cantidad_vendida = leer_entero("Cantidad a vender: ", 1)

    conexion = conectar()

    try:
        # Inicio de la transaccion: aun no se confirma nada.
        conexion.execute("BEGIN")

        producto = conexion.execute(
            """SELECT nombre, precio, cantidad
               FROM productos WHERE id = ?""",
            (producto_id,)
        ).fetchone()

        if producto is None:
            raise ValueError("El producto no existe.")

        nombre, precio, disponible = producto

        if disponible < cantidad_vendida:
            raise ValueError(
                f"Existencias insuficientes. Disponibles: {disponible}"
            )

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Primera operacion: registrar la venta.
        conexion.execute(
            """INSERT INTO ventas (producto_id, cantidad, fecha)
               VALUES (?, ?, ?)""",
            (producto_id, cantidad_vendida, fecha)
        )

        # Segunda operacion: descontar el inventario.
        # Si hay un error aqui, se cancela tambien la venta.
        conexion.execute(
            """UPDATE productos
               SET cantidad = cantidad - ?
               WHERE id = ? AND cantidad >= ?""",
            (cantidad_vendida, producto_id, cantidad_vendida)
        )

        if conexion.execute("SELECT changes()").fetchone()[0] != 1:
            raise RuntimeError("No se pudo actualizar el inventario.")

        # Confirmar las dos operaciones juntas.
        conexion.commit()

        total = precio * cantidad_vendida
        print("\nVenta registrada correctamente.")
        print("Producto:", nombre)
        print("Cantidad:", cantidad_vendida)
        print(f"Total de la venta: ${total:.2f}")

    except (ValueError, RuntimeError, sqlite3.Error) as error:
        conexion.rollback()
        print("Venta cancelada:", error)
        print("Se revirtieron los cambios de la transaccion.")

    finally:
        conexion.close()


def historial_ventas():
    with conectar() as conexion:
        ventas = conexion.execute("""
            SELECT ventas.id, productos.nombre,
                   ventas.cantidad, productos.precio,
                   ventas.fecha
            FROM ventas
            INNER JOIN productos
                ON ventas.producto_id = productos.id
            ORDER BY ventas.id DESC
        """).fetchall()

    if not ventas:
        print("No hay ventas registradas.")
        return

    print("\n--- HISTORIAL DE VENTAS ---")
    for venta in ventas:
        venta_id, nombre, cantidad, precio, fecha = venta
        print(
            f"Venta #{venta_id} | {nombre} | "
            f"Cantidad: {cantidad} | "
            f"Precio actual: ${precio:.2f} | "
            f"Fecha: {fecha}"
        )


def demostrar_rollback():
    """Prueba controlada: simula un error despues del INSERT."""
    conexion = conectar()

    try:
        conexion.execute("BEGIN")

        producto = conexion.execute(
            "SELECT id FROM productos ORDER BY id LIMIT 1"
        ).fetchone()

        if producto is None:
            print("Primero registra al menos un producto.")
            conexion.rollback()
            return

        producto_id = producto[0]

        antes = conexion.execute(
            "SELECT COUNT(*) FROM ventas"
        ).fetchone()[0]

        # Insercion temporal dentro de la transaccion.
        conexion.execute(
            """INSERT INTO ventas (producto_id, cantidad, fecha)
               VALUES (?, ?, ?)""",
            (producto_id, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

        print("Venta temporal insertada dentro de la transaccion.")
        print("Provocando un error controlado...")

        # Error intencional para demostrar rollback.
        raise RuntimeError("Error de prueba antes de actualizar stock.")

    except RuntimeError as error:
        conexion.rollback()
        print("Error controlado:", error)

        despues = conexion.execute(
            "SELECT COUNT(*) FROM ventas"
        ).fetchone()[0]

        print("Ventas antes de la prueba:", antes)
        print("Ventas despues del rollback:", despues)

        if antes == despues:
            print("PRUEBA EXITOSA: los datos quedaron intactos.")
        else:
            print("ERROR: los datos no coinciden.")

    except sqlite3.Error as error:
        conexion.rollback()
        print("Error de SQLite:", error)

    finally:
        conexion.close()


def menu():
    crear_tablas()

    while True:
        print("\n===== SISTEMA DE INVENTARIO Y VENTAS =====")
        print("1. Registrar producto")
        print("2. Consultar productos")
        print("3. Actualizar producto")
        print("4. Eliminar producto")
        print("5. Registrar venta")
        print("6. Historial de ventas")
        print("7. Demostrar rollback")
        print("0. Salir")

        opcion = input("Selecciona una opcion: ").strip()

        if opcion == "1":
            registrar_producto()
        elif opcion == "2":
            consultar_productos()
        elif opcion == "3":
            actualizar_producto()
        elif opcion == "4":
            eliminar_producto()
        elif opcion == "5":
            registrar_venta()
        elif opcion == "6":
            historial_ventas()
        elif opcion == "7":
            demostrar_rollback()
        elif opcion == "0":
            print("Programa finalizado.")
            break
        else:
            print("Opcion no valida. Intenta nuevamente.")


if __name__ == "__main__":
    menu()