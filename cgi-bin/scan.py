#!/usr/bin/env python3

import cgitb
import datetime
import requests
import xml.etree.ElementTree as ET
import os
from PIL import Image, ImageStat, ImageChops
import pytesseract
import codecs

cgitb.enable()
print("Content-type: text/plain\r\n\r\n")

today = datetime.date.today()




PRINTER_HOST = 'hpc8d9d2496135.local'

SAVE_PREFIX = '/octal/shared/Scanner/'
SAVE_PATH = SAVE_PREFIX + '{:%Y-%m-%d}'.format(today)

SCAN_RESOLUTION = 300
SCAN_FORMAT = "image/jpeg" # application/pdf or image/jpeg
SCAN_COLOR_MODE = "Grayscale8" # BlackAndWhite1 or Grayscale8 or RGB24
SCAN_BRIGHTNESS = 1000 # from 0 to 2000, 1000 is normal
SCAN_CONTRAST = 1000 # from 0 to 2000, 1000 is normal



os.makedirs(SAVE_PATH, exist_ok=True)
os.chmod(SAVE_PATH, 0o777)

file_no = 0
file_max = None

for entry in os.listdir(SAVE_PATH):
    name = os.path.splitext(entry)[0]
    try:
        if int(name) > file_no:
            file_no = int(name)
            file_max = entry
    except Exception:
        pass

SAVE_FILENAME = '{0:03d}'.format(file_no + 1)



if os.environ['REQUEST_METHOD'] == 'GET':
    print("Please send POST request.")
    exit()


# https://hpc8d9d2496135.local./eSCL/ScannerCapabilities
r = requests.post('http://' + PRINTER_HOST + '/eSCL/ScanJobs', data="""
    <scan:ScanSettings 
        xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03" 
        xmlns:dd="http://www.hp.com/schemas/imaging/con/dictionaries/1.0/" 
        xmlns:dd3="http://www.hp.com/schemas/imaging/con/dictionaries/2009/04/06" 
        xmlns:fw="http://www.hp.com/schemas/imaging/con/firewall/2011/01/05" 
        xmlns:scc="http://schemas.hp.com/imaging/escl/2011/05/03" 
        xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
        <pwg:Version>2.1</pwg:Version>
        <scan:Intent>Document</scan:Intent>
        <pwg:ScanRegions>
            <pwg:ScanRegion>
                <pwg:Height>3300</pwg:Height>
                <pwg:Width>2550</pwg:Width>
                <pwg:XOffset>0</pwg:XOffset>
                <pwg:YOffset>0</pwg:YOffset>
            </pwg:ScanRegion>
        </pwg:ScanRegions>
        <pwg:InputSource>Platen</pwg:InputSource>
        <scan:DocumentFormatExt>"""  + SCAN_FORMAT + """</scan:DocumentFormatExt>
        <scan:XResolution>""" + str(SCAN_RESOLUTION) + """</scan:XResolution>
        <scan:YResolution>""" + str(SCAN_RESOLUTION) + """</scan:YResolution>
        <scan:ColorMode>""" + SCAN_COLOR_MODE + """</scan:ColorMode>
        <scan:CompressionFactor>25</scan:CompressionFactor>
        <scan:Brightness>""" + str(SCAN_BRIGHTNESS) + """</scan:Brightness>
        <scan:Contrast>""" + str(SCAN_CONTRAST) + """</scan:Contrast>
    </scan:ScanSettings>
""")


r = requests.get('http://' + PRINTER_HOST + '/eSCL/ScannerStatus')


SCAN_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
}

root = ET.fromstring(r.text)
ns = {
    'scan': "http://schemas.hp.com/imaging/escl/2011/05/03",
    'pwg': "http://www.pwg.org/schemas/2010/12/sm"
}


for job in root.findall('scan:Jobs/scan:JobInfo', namespaces=ns):
    uri = job.find('pwg:JobUri', namespaces=ns).text
    status = job.find('pwg:JobState', namespaces=ns).text

    if status == 'Processing':
        r = requests.get('http://' + PRINTER_HOST + uri + '/NextDocument')
        
        FILENAME = os.path.join(SAVE_PATH, SAVE_FILENAME + SCAN_EXTENSIONS[SCAN_FORMAT])
        with open(FILENAME, 'wb') as f:
            f.write(r.content)

        os.chmod(FILENAME, 0o777)
        
        im = Image.open(FILENAME)
        gray = im.convert('L')
        thumb_size = (512, 512)
        gray.thumbnail(thumb_size, Image.ANTIALIAS)
        
        stats = ImageStat.Stat(gray)


        dstat = None
        try:
            maxim = Image.open(os.path.join(SAVE_PATH, file_max)).convert('L')
            maxim.thumbnail(thumb_size, Image.ANTIALIAS)

            dstat = ImageStat.Stat(ImageChops.difference(maxim, gray))
        except Exception as e:
            print(e)
            pass

        should_remove = False


        with codecs.open(SAVE_PREFIX + 'log.txt', 'a', encoding='utf-8') as f:
            f.write('===== ' + FILENAME + ' =====\n\n')
            
            if stats.mean[0] > 254 and stats.stddev[0] < 1:
                should_remove = True

            f.write(repr({
                'mean': stats.mean,
                'sum2': stats.sum2,
                'sum': stats.sum,
                'median': stats.median,
                'stdev': stats.stddev
            }))
            if dstat:
                f.write('\nDifference from previous image:\n')
                f.write(repr({
                    'mean': dstat.mean,
                    'sum2': dstat.sum2,
                    'sum': dstat.sum,
                    'median': dstat.median,
                    'stdev': dstat.stddev
                }))

                if dstat.mean[0] < 2:
                    should_remove = True
            
            if should_remove:
                f.write('\nRemoving file....')

            f.write('\n\n\n')
            

        if should_remove:
            os.remove(FILENAME)
            print('removed file')    
        else:
            text = pytesseract.image_to_string(im)

            with codecs.open(SAVE_PREFIX + 'scans.txt', 'a', encoding='utf-8') as f:
                f.write('===== ' + FILENAME + ' =====\n\n')
                
                f.write(text)
                f.write('\n\n\n\n')

            print('finished ocr')
