from pdf2image import convert_from_path
from PIL import Image
import pytesseract

def handle_uploaded_file(uploaded_file, target_path):
    # Create a new file in write-binary mode
    with open(target_path, 'wb') as destination:
        # Write the contents of the uploaded file to the new file
        destination.write(uploaded_file.read())  # Read the entire content at once
    
    # Return the path of the saved file
    return target_path

def pdf_to_image(pdf_path):
    images = convert_from_path(pdf_path)

    # Calculate the total height of all images (assuming they have the same width)
    total_height = sum(img.size[1] for img in images)
    max_width = max(img.size[0] for img in images)

    # Create a new image with the appropriate height and width
    combined_image = Image.new('RGB', (max_width, total_height))

    # Paste the images together
    y_offset = 0
    for img in images:
        combined_image.paste(img, (0, y_offset))
        y_offset += img.size[1]

    return combined_image

class Prompt:
    
    def __init__(self):
        self.pdf_template = '''
        from reportlab.pdfgen import canvas
from reportlab.platypus import (SimpleDocTemplate, Paragraph, PageBreak, Image, Spacer, Table, TableStyle)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import LETTER, inch
from reportlab.graphics.shapes import Line, LineShape, Drawing
from reportlab.lib.colors import Color

class FooterCanvas(canvas.Canvas):

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
        self.width, self.height = LETTER

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            if (self._pageNumber > 1):
                self.draw_canvas(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_canvas(self, page_count):
        page = "Page %s of %s" % (self._pageNumber, page_count)
        x = 128
        self.saveState()
        self.setStrokeColorRGB(0, 0, 0)
        self.setLineWidth(0.5)
        self.drawImage("static/lr.png", self.width-inch*8-5, self.height-50, width=100, height=20, preserveAspectRatio=True)
        self.drawImage("static/ohka.png", self.width - inch * 2, self.height-50, width=100, height=30, preserveAspectRatio=True, mask='auto')
        self.line(30, 740, LETTER[0] - 50, 740)
        self.line(66, 78, LETTER[0] - 66, 78)
        self.setFont('Times-Roman', 10)
        self.drawString(LETTER[0]-x, 65, page)
        self.restoreState()

class PDFPSReport:

    def __init__(self, path, data):
        self.data = data
        self.path = path
        self.styleSheet = getSampleStyleSheet()
        self.elements = []

        # colors - Azul turkeza 367AB3
        self.colorOhkaBlue0 = Color((54.0/255), (122.0/255), (179.0/255), 1)
        self.colorOhkaBlue1 = Color((122.0/255), (180.0/255), (225.0/255), 1)
        self.colorOhkaGreenLineas = Color((50.0/255), (140.0/255), (140.0/255), 1)
        
        for key in data:
        
            self.TableMaker(key)
            self.elements.append(PageBreak())
        
        # Build
        self.doc = SimpleDocTemplate(path, pagesize=LETTER)
        self.doc.multiBuild(self.elements, canvasmaker=FooterCanvas)

    def TableMaker(self, title):        
        psHeaderText = ParagraphStyle('Hed0', fontSize=12, alignment=TA_LEFT, borderWidth=3, textColor=self.colorOhkaBlue0)
        text = title
        paragraphReportHeader = Paragraph(text, psHeaderText)
        self.elements.append(paragraphReportHeader)

        spacer = Spacer(10, 22)
        self.elements.append(spacer)
        """
        Create the line items
        """
        d = []
        textData = ["No.", "Date", "Hour Started", "Hour Finished", "Total Time"]
                
        fontSize = 8
        centered = ParagraphStyle(name="centered", alignment=TA_CENTER)
        for text in textData:
            ptext = "<font size='%s'><b>%s</b></font>" % (fontSize, text)
            titlesTable = Paragraph(ptext, centered)
            d.append(titlesTable)        

        data = [d]
        lineNum = 1
        formattedLineData = []

        alignStyle = [ParagraphStyle(name="01", alignment=TA_CENTER),
                      ParagraphStyle(name="02", alignment=TA_LEFT),
                      ParagraphStyle(name="03", alignment=TA_CENTER),
                      ParagraphStyle(name="04", alignment=TA_CENTER),
                      ParagraphStyle(name="05", alignment=TA_CENTER)]

        for row in range(10):
            lineData = [str(lineNum), "Tuesday, November 28, 2023", 
                                            "17:30", "19:24", "1:54"]
            #data.append(lineData)
            columnNumber = 0
            for item in lineData:
                ptext = "<font size='%s'>%s</font>" % (fontSize-1, item)
                p = Paragraph(ptext, alignStyle[columnNumber])
                formattedLineData.append(p)
                columnNumber = columnNumber + 1
            data.append(formattedLineData)
            formattedLineData = []
            
        # Row for total
        totalRow = ["Total Hours", "", "", "", "30:15"]
        for item in totalRow:
            ptext = "<font size='%s'>%s</font>" % (fontSize-1, item)
            p = Paragraph(ptext, alignStyle[1])
            formattedLineData.append(p)
        data.append(formattedLineData)
        
        #print(data)
        table = Table(data, colWidths=[50, 200, 80, 80, 80])
        tStyle = TableStyle([ #('GRID',(0, 0), (-1, -1), 0.5, grey),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                #('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ("ALIGN", (1, 0), (1, -1), 'RIGHT'),
                ('LINEABOVE', (0, 0), (-1, -1), 1, self.colorOhkaBlue1),
                ('BACKGROUND',(0, 0), (-1, 0), self.colorOhkaGreenLineas),
                ('BACKGROUND',(0, -1),(-1, -1), self.colorOhkaBlue1),
                ('SPAN',(0,-1),(-2,-1))
                ])
        table.setStyle(tStyle)
        self.elements.append(table)


if __name__ == '__main__':
    
    data = ["Remote Sessions", "On-Site Sessions", "Other Activities"]
    
    name = 'invoice.pdf'
    
    report = PDFPSReport(name, data)
        '''