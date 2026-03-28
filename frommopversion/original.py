### Created by Juan Carlos Figueroa. INRHED spa

### Modified by SQPaul

import time

import datetime

import tkinter as tk

from tkinter import messagebox

from selenium import webdriver

from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import TimeoutException

#from selenium.webdriver.support.ui import Select


# Configurar el navegador

driver = webdriver.Chrome(r"C:\SeleniumDrivers\chromedriver.exe") ## [TOKEN] En este paso descargar chromedriver desde esta pÃ¡gina https://chromedriver.chromium.org/downloads. Una vez descargado ir a la carpeta seleniundriver, descomprimir y copiar .exe en el path de la variable "driver" 

driver.get('https://snia.mop.gob.cl/BNAConsultas/reportes')

# FunciÃ³n para descargar los datos

def descargar_datos():

    # Esperar a que el usuario complete el recaptcha

    # Esperar a que se cargue el recaptcha

    #captcha = WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.ID, "recaptcha-anchor")))

    # Esperar a que el usuario complete el recaptcha 

    #while captcha.get_attribute("aria-checked") == "false":

    #    time.sleep(1)

    #driver.switch_to.default_content()

    # Obtener fechas inicial y final ingresadas por el usuario

    fecha_inicial = fecha_inicial_entry.get()

    fecha_final = fecha_final_entry.get()

    # Convertir las fechas ingresadas por el usuario en objetos datetime

    fecha_inicial = datetime.datetime.strptime(fecha_inicial, '%d/%m/%Y')

    fecha_final = datetime.datetime.strptime(fecha_final, '%d/%m/%Y')

    # Generar las fechas de 4 en 4 aÃ±os e imprimir cada par de fechas

    #try:

    for i in range(fecha_inicial.year, fecha_final.year+1, 4):

        fecha_inicio = datetime.datetime(i, 1, 1)

        fecha_fin = datetime.datetime(i+3, 12, 31)

        if fecha_fin >= fecha_inicial and fecha_inicio <= fecha_final:

            fecha_desde_var = (fecha_inicio.strftime('%d/%m/%Y'))

            fecha_hasta_var = (fecha_fin.strftime('%d/%m/%Y'))

        fecha_desde = WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.NAME, "filtroscirhform:fechaDesdeInputDate")))

        fecha_desde.clear()

        fecha_desde.send_keys(fecha_desde_var)

        fecha_hasta = WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.NAME, "filtroscirhform:fechaHastaInputDate")))

        fecha_hasta.clear()

        fecha_hasta.send_keys(fecha_hasta_var)

        descargar_xl = WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.NAME, "filtroscirhform:generarxls")))

        descargar_xl.click()

        boton_no_esta = WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.XPATH, '//*[@id="popupInfoMessage_header_controls"]/a')))

        if boton_no_esta.is_displayed():

            time.sleep(1)

            boton_no_esta.click()

            time.sleep(2)

            #driver.switch_to.default_content()

            #fecha_desde = WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.NAME, "filtroscirhform:fechaDesdeInputDate")))

            #fecha_hasta = WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.NAME, "filtroscirhform:fechaHastaInputDate")))

            #fecha_desde.clear()

            #fecha_hasta.clear()

            continue

        # Esperar a que el archivo se descargue completamente

        time.sleep(30)

        fecha_desde.clear()

        fecha_hasta.clear()

        # Mostrar la ventana emergente

    messagebox.showinfo("Descarga finalizada!", "La descarga de los datos ha finalizado.")

    #except Exception as e:

        #print("erroor:",e)

# Crear la ventana principal

ventana = tk.Tk()

ventana.title("Asistente de descarga")

# Crear los widgets

mensaje_label = tk.Label(ventana, text='''Â¿CÃ³mo usar?

1. Espere que cargue la pÃ¡gina web de la DGA. 

2. Seleccione el tipo de informe.

3. En â€œBÃºsqueda de estacionesâ€ seleccione: â€œRegiÃ³n:â€, â€œBuscar por:â€ y â€œCuenca HidrogrÃ¡fica:â€.

4. Presione el reCAPTCHA y complÃ©telo por favor.

5. Presione â€œBuscarâ€.

6. Seleccione la estaciÃ³n de la que desea descargar sus datos.

7. Escriba las fechas inicial y final en el Asistente de descarga. Puede ser cualquier rango, el programa salta automÃ¡ticamente si no se encuentra en DGA.

8. Presione â€œContinuarâ€.

9. Espere a que se descarguen todos los Excel en bloques de 4 aÃ±os hasta completar el periodo seleccionado.''', justify="left")

fecha_inicial_label = tk.Label(ventana, text="Fecha inicial (dd/mm/yyyy):")

fecha_inicial_entry = tk.Entry(ventana)

fecha_final_label = tk.Label(ventana, text="Fecha final (dd/mm/yyyy):")

fecha_final_entry = tk.Entry(ventana)

continuar_boton = tk.Button(ventana, text="Continuar", command=lambda: descargar_datos())

progreso_label = tk.Label(ventana, text="Tiempo aproximado: 30 segundos por cada Excel descargado.")

# Ubicar los widgets en la ventana

mensaje_label.grid(row=0, column=0, columnspan=2)

fecha_inicial_label.grid(row=2, column=0)

fecha_inicial_entry.grid(row=2, column=1)

fecha_final_label.grid(row=3, column=0)

fecha_final_entry.grid(row=3, column=1)

continuar_boton.grid(row=4, column=0, columnspan=2)

progreso_label.grid(row=5, column=0, columnspan=2)


#Mostrar la ventana

ventana.mainloop()

WebDriverWait(driver, 10)
Downloads  |  ChromeDriver  |  Chrome for Developers
 