import geodownload as g
import PySimpleGUI as sg
import os

working_directory = os.getcwd()

##----LAYOUT DEFINITION
layout = [  
            [sg.Text("Input TERYT code:")],
            [sg.InputText(key="-TERYT-", size=(100,1))], 
            [sg.Text("Input buffer (distance outside of parcel to aquire in meters):")],
            [sg.InputText(key="-BUFFER-", size=(100,1))],
            [sg.Text("Choose folder:")],
            [sg.InputText(key="-FOLDER_PATH-", size=(88,1)), 
            sg.FolderBrowse(initial_folder=working_directory)],
            [sg.Multiline(size=(98,50), key="-INFO-", default_text="Warning! Early version can hang Your computer.\nProgram work only on small parcels",auto_refresh=True)],
            [sg.Button('Submit'), sg.Exit()]
        ]

window = sg.Window("Download Geoportal data as DXF ver.0.1 alpha", layout)

##----EVENT HANDLER
while True:
    event, values = window.read()
    if event in (sg.WIN_CLOSED, 'Exit'):
        break
    elif event == "Submit":
        teryt = values["-TERYT-"]
        address = values["-FOLDER_PATH-"]
        buffer = values["-BUFFER-"]
        try:
            g.geo(teryt, buffer, address)
            window['-INFO-'].print("DXF created succefully. Check if all images works propoerly", text_color='black')
        except ValueError as err:
            window['-INFO-'].print(err, text_color='red')


window.close()

