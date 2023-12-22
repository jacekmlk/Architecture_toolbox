# ARCHITECTURE TOOLBOX 

Set of tools to speed up architecture process.
Tools are suited to polish market

## 1. GEOTODXF

Download data from geoportal.gov.pl and save in dxf file in local CRS.

**Input:** TERYT CODE

**Output:** DXF file incorporating:
1. Działka ULDK - vector
1. EGIB - Ewidencja gruntów i budynków - raster
1. KIUT - Krajowa integracja uzbrojenia terenu - raster
1. Obiekty topograficzne BDOT 500 - raster
1. Ortofoto HQ - raster
1. MPZP - raster


**TODO:**
1. !Resolve issues wit making build!
1. Building - vector
1. NMT - to check
1. MPZP Get Feature
1. Better errorhandling on request
1. Resolve balckouts as result of transformation

## 2. Vector_Polish_sunlight_hours_compilance

Rhino Grasshopper/Ladybug daylight analysys definition.  
This definition generate hour-by hour shadow analysys. Output is set of colored polylines.  
Default time are spring and autumn eqquinox.  

## 3. Accurate_Polish_sunlight_hours_compilance

Rhino Grasshopper/Ladybug daylight analysys definition.  
This definition generate map of time that shadow occur in speciffied area.   
Default time are spring and autumn eqquinox. 
