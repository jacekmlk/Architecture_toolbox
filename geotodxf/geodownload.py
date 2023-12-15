import rasterio
import requests
import re
import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf import zoom
import shapely.wkt
from pyproj import Transformer
from shapely.geometry import Polygon
from rasterio.warp import calculate_default_transform, reproject, transform_bounds, Resampling
from rasterio.transform import from_bounds


def geo(teryt, bufferInput, pathInput):
    resolution = 0.05

    #---- Handle Input Errors
    if bufferInput.isnumeric() == False or bufferInput == '':
        raise ValueError("Buffer must be a number!")
    
    m = re.fullmatch(r'^[0-9]{6}_[\w_/.//]*', teryt)
    if not m:
        raise ValueError("Wrong TERYT number!")
    
    if pathInput == '':
        raise ValueError("Input file location")
        
    #----1. Request data from ULDK
    folder = pathInput + '/'

    #----CRS handling
    crs = str(findCRS(teryt))

    # 2. Add handling list of parcels
    request = requests.get("https://uldk.gugik.gov.pl/?request=GetParcelById&id=" + teryt + "&srid=" + "2180" + "&result=geom_wkt,geom_extent,voivodeship,county,commune,region,parcel")

    #---- Handle request Errors
    request.raise_for_status()

    data = request.text
    if data[0] != '0':
        raise ValueError("Error!\nResponse from server: " + data + '\n' + str(request.status_code))

    #----1.1 slice into set of data
    data = data.removeprefix("0\n").removesuffix("\n")
    dataList = re.split("[;|]+", data)

    #----1.2 convert to dictionary
    parcelData = {
        "srid":dataList[0],
        "geom_wkt":dataList[1],
        "geom_extent":dataList[2],
        "voivodeship":dataList[3],
        "county":dataList[4],
        "commune":dataList[5],
        "region":dataList[6],
        "parcel":dataList[7],
        "teryt":teryt
    }
    print("extend:", parcelData["geom_extent"])

    #----Add filename
    filename = parcelData["teryt"].replace('.', '_')
    filename = filename.replace('/', '_')

    #----2. Convert Parcel WKT to Shapely polyline
    parcelPoly = shapely.wkt.loads(parcelData["geom_wkt"])
    parcelPolygon = transformVector(parcelPoly, 2180, crs) # Transformation of polygon
    parcelCenter = parcelPolygon.centroid

    #---- Get parcel area
    area = round(parcelPolygon.area, 2)

    #----2.1 Convert extent to Shapely polyline
    BBox = getBBox(parcelPoly, bufferInput, resolution)
    BBoxA = getBBox(parcelPolygon, bufferInput, resolution)

    #---- Add imagepath
    imgPath = folder + filename + '_'

    #==== START DXF FILE ====
    doc = ezdxf.new("R2010", setup=True)
    doc.header['$INSUNITS'] = 6
    doc.header['$MEASUREMENT'] = 1

    msp = doc.modelspace()

    # 2.3 Get Ortofoto

    ortofotoHQ_img = getCoverage("https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS/HighResolution", "FORMAT=image/jpeg&COVERAGE=Orthoimagery_High_Resolution", BBox, 0.05)
    if ortofotoHQ_img != None:
        ortofotoHQ_img["name"] = "ortofotoHQ"
        processImage(ortofotoHQ_img, imgPath, BBox, doc, msp, "jpeg", crs)


    # 2.4 Get KIEG

    KIEG_img = getMap("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow", "LAYERS=dzialki,numery_dzialek,budynki", BBox, 0.05)
    if KIEG_img != None:
        KIEG_img["name"] = "dzialki_i_budynki"
        processImage(KIEG_img, imgPath, BBox, doc, msp, "png", crs)


    # 2.4 Get KIUT
    KIUT_img = getMap("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaUzbrojeniaTerenu", "LAYERS=przewod_urzadzenia,przewod_niezidentyfikowany,przewod_specjalny,przewod_telekomunikacyjny,przewod_gazowy,przewod_cieplowniczy,przewod_wodociagowy,przewod_kanalizacyjny,przewod_gazowy,przewod_elektroenergetyczny", BBox, 0.05)
    if KIUT_img !=None:
        KIUT_img["name"] = "sieci"
        processImage(KIUT_img, imgPath, BBox, doc, msp, "png", crs)

    
    # 2.4 Get KIBDOT

    KIBDOT_img = getMap("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaBazDanychObiektowTopograficznych", "LAYERS=bdot", BBox, 0.05)
    if KIBDOT_img !=None:
        KIBDOT_img["name"] = "obiekty_topo"
        processImage(KIBDOT_img, imgPath, BBox, doc, msp, "png", crs)

    
    # 2.5 Get MPZP

    MPZP_img = getMap("https://mapy.geoportal.gov.pl/wss/ext/KrajowaIntegracjaMiejscowychPlanowZagospodarowaniaPrzestrzennego", "LAYERS=granice,plany_granice,raster,wektor-str,wektor-lzb,wektor-pow,wektor-lin,wektor-pkt,granice", BBox, 0.05)
    if MPZP_img !=None:
        MPZP_img["name"] = "mpzp"
        processImage(MPZP_img, imgPath, BBox, doc, msp, "png", crs)

    
    #======================================= DXF creation ===============================================
    #----3.1 Add ULDK to file
    #----3.1.1 Create ULDK layer
    doc.layers.add(name="PZT_dzialka", color=5)#----Adjust to standard
    doc.layers.add(name="PZT_text", color=7)

    points = list(parcelPolygon.exterior.coords)
    msp.add_lwpolyline(points, dxfattribs={"layer": "PZT_dzialka"})


    #----3.2 Add parcel number
    msp.add_text(parcelData["parcel"], height=1.25, dxfattribs={"layer": "PZT_dzialka", "style":"LiberationMono"}).set_placement((parcelCenter.x, parcelCenter.y), align=TextEntityAlignment.MIDDLE_CENTER)

    #---- Add parcel info
    textInput = f"TERYT: {parcelData['teryt']}\nWojewództwo {parcelData['voivodeship']}\nPowiat {parcelData['county']}\nGmina {parcelData['commune']}\nObręb {parcelData['region']}\nNumer ewidencyjny {parcelData['parcel']}\nUkład odniesienia EPSG: {crs}\nPowierzchnia: {area} m2"
    mtext = msp.add_mtext(textInput, dxfattribs={"layer": "PZT_text", "style":"LiberationMono"})
    mtext.dxf.char_height = 1.25
    mtext.set_location(insert=(BBoxA[2] + 5, BBoxA[3] + 5))

    image_defs = doc.objects.query("IMAGEDEF")
    
    zoom.extents(msp)
    doc.saveas(folder + filename +".dxf")

    print("\n==================================\nDXF created succefully!")


def findCRS(teryt):
    # Function finds best CRS
    query = requests.get("https://uldk.gugik.gov.pl/?request=GetParcelById&id=" + teryt +"&srid=4326&result=geom_wkt")

    #---- Handle request Errors
    query.raise_for_status()

    data = query.text
    if data[0] != '0':
        raise ValueError("Error!\nResponse from server: " + data + '\n' + str(query.status_code))

    #----1.1 slice into set of data
    data = data.removeprefix("0\n").removesuffix("\n")
    dataList = re.split("[;|]+", data)

    parcel = shapely.wkt.loads(dataList[1])

    center = parcel.centroid
    lon = center.x

    # 1. Check which of CRS is on area: EPSG 2176, 2177, 2178, 2179
    crs_code = ""
    if lon >= 14.14 and lon < 16.5:
        crs_code = 2176
    if lon >= 16.5 and lon < 19.5:
        crs_code = 2177
    if lon >= 19.5 and lon < 22.5:
        crs_code = 2178
    if lon >= 22.5 and lon < 24.15:
        crs_code = 2179

    return crs_code

def getBBox(parcelPolygon, bufferInput, resolution):
    extentBounds = list(parcelPolygon.bounds)

    bound = int(bufferInput)
    BBox = [int(extentBounds[0] - bound), int(extentBounds[1] - bound), int(extentBounds[2] + bound), int(extentBounds[3] + bound)]

    widthpx = int((BBox[2] - BBox[0]) / resolution)
    heightpx = int((BBox[3] - BBox[1]) / resolution)

    widthm = resolution * widthpx
    heightm = resolution * heightpx

    BBox[2] = BBox[0] + widthm
    BBox[3] = BBox[1] + heightm

    return BBox


def transformVector(polygon, from_crs, to_crs):
    # 2. Translate from EPSG 2180 to chosen EPSG
    # 2A. Transform polygon
    transf = Transformer.from_crs(int(from_crs), int(to_crs), always_xy=True)

    ptlist_crs = []
    for pt in list(polygon.exterior.coords):
        ptlist_crs.append(transf.transform(pt[0], pt[1]))

    # Convert to shapely
    return Polygon(ptlist_crs)


def pathSlice(path):
    pieces = path.rpartition("/")
    suffix = pieces[2].rpartition(".")
    
    return [pieces[0] + pieces[1] + suffix[0], suffix[1] + suffix[2]]


def transformRaster(raster, Bbox, from_crs, to_crs):
    srcCrs = {"init":f'EPSG:{from_crs}'}
    dstCrs = {"init":f'EPSG:{to_crs}'}

    path = pathSlice(raster)
    rasterPath = path[0] + str(to_crs) + path[1]

    with rasterio.open(raster) as src:
        width = src.width
        height = src.height
        west = Bbox[0]
        south = Bbox[1]
        east = Bbox[2]
        north = Bbox[3]
        
        src_transform = from_bounds(west, south, east, north, width, height)
        dst_transform, dst_width, dst_height = calculate_default_transform(srcCrs, dstCrs, width, height, west, south, east, north)
        dstBox = transform_bounds(srcCrs, dstCrs, west, south, east, north)

        kwargs = src.meta.copy()
        kwargs.update({
                'crs': dstCrs,
                'transform': dst_transform,
                'width': dst_width,
                'height': dst_height
            })
        with rasterio.open(rasterPath, 
                           'w',
                            **kwargs,
                           ) as dst:
            for i in range(1 , src.count + 1):
                reproject(
                    source=src.read(i),
                    destination=rasterio.band(dst, i),
                    src_transform=src_transform,
                    src_crs=srcCrs,
                    dst_transform=dst_transform,
                    dst_crs=dstCrs,
                    resampling=Resampling.bilinear)
            dst.close()
        src.close()

        return rasterPath, dstBox, dst_width, dst_height


def getCoverage(url, arguments, extent, resolution):
    crs = "2180"
    print("\nAsking server for:", url)
    widthpx = int((extent[2] - extent[0]) / resolution)
    heightpx = int((extent[3] - extent[1]) / resolution)

    if widthpx > 4000 or heightpx > 4000:
        w_h = widthpx/heightpx
        if widthpx >= heightpx:
            widthpx = 4000
            heightpx = widthpx / w_h
        else:
            heightpx = 4000
            widthpx = w_h * heightpx
    print("Imagesize_px: ", widthpx, "x", heightpx)
    print("Imagesize_m ", extent[2] - extent[0], "x", extent[3] - extent[1])

    request = url + "?SERVICE=WCS&VERSION=1.0.0&REQUEST=GetCoverage&" + arguments + "&BBOX=" + str(extent[0]) + ',' + str(extent[1]) + ',' + str(extent[2]) + ',' + str(extent[3]) + "&CRS=EPSG:"+ crs +"&RESPONSE_CRS=EPSG:"+ crs +"&WIDTH=" + str(widthpx) + "&HEIGHT=" + str(heightpx)

    #----TODO: Add errorhandling
    try:
        response = requests.get(request, timeout=120)
        response.raise_for_status()
    except:
        print("\nServer Error!\n", response)
        return None

    print(url + "\nresponse: " + str(response))
    
    output = {}
    output["img"] = response.content
    output["size"] = (widthpx, heightpx)

    return output


def getMap(url, arguments, extent, resolution):
    crs = "2180"
    print("\nAsking server for: "+ url)
    
    widthpx = int((extent[2] - extent[0]) / resolution)
    heightpx = int((extent[3] - extent[1]) / resolution)

    #Add max width, max height handling
    #Shortcut - If max resolution is achieved - > cut off resolution to maximum capable
    if widthpx > 3840 or heightpx > 3840:
        w_h = widthpx/heightpx
        if widthpx >= heightpx:
            widthpx = 3840
            heightpx = widthpx / w_h
        else:
            heightpx = 3840
            widthpx = w_h * heightpx
    
    print("Imagesize_px: ", widthpx, "x", heightpx)
    print("Imagesize_m ", extent[2] - extent[0], "x", extent[3] - extent[1])

    request = url + "?VERSION=1.1.1&SERVICE=WMS&REQUEST=GetMap&TRANSPARENT=TRUE&FORMAT=image/png&SRS=EPSG:"+ crs +"&" + arguments + "&BBOX=" + str(extent[0]) + ',' + str(extent[1]) + ',' + str(extent[2]) + ',' + str(extent[3]) + "&WIDTH=" + str(widthpx) + "&HEIGHT=" + str(heightpx)

    print(request)
    #----TODO: Add errorhandling
    try:
        response = requests.get(request, timeout=120)
        response.raise_for_status()
    except:
        print("\nServer Error!\n", response)
        return None
    
    output = {}
    output["img"] = response.content
    output["size"] = (widthpx, heightpx)
    print("Image downloaded succefully!")

    return output


def processImage(image, imgPath, extends, doc, msp, imageType, crs):
    if image == None:
        return None
    
    imgName = imgPath + image["name"] +'.'+ imageType
    
    #----1. Create and save file
    f = open(imgName, "wb")
    f.write(image["img"])
    f.close()
    print(image["name"] + "." + imageType + " - image saved")

    #----1.A Convert image to desired CRS
    reprojectImgName, BBox, width, height = transformRaster(imgName, extends, "2180", crs)

    #----2. Create ezxdxf definition
    image_def = doc.add_image_def(filename=reprojectImgName, size_in_pixel=(width, height))
    
    #----3. Create ezdxf layer
    doc.layers.add(name="PZT_" + image["name"], color=7,)
    print("PZT_" + image["name"] +" - layer created.")

    #----4. Add image
    image_entity = msp.add_image(
        insert=((BBox[0], BBox[1])),
        size_in_units=(BBox[2] - BBox[0] , BBox[3] - BBox[1]),
        image_def=image_def,
        rotation=0,
        dxfattribs={"layer": "PZT_" + image["name"]},
    )
    image_entity.flags = 8

    print(image["name"] +"." + imageType + " - image loaded into dxf.")


