import frappe, os
from frappe import _

from frappe.utils.pdf import get_pdf,cleanup
from frappe.core.doctype.access_log.access_log import make_access_log
from PyPDF2 import PdfFileWriter

no_cache = 1

base_template_path = "www/printview.html"
standard_format = "templates/print_formats/standard.html"

@frappe.whitelist()
def download_multi_pdf(doctype, name, format=None, no_letterhead=0):
	"""
	Concatenate multiple docs as PDF .

	Returns a PDF compiled by concatenating multiple documents. The documents
	can be from a single DocType or multiple DocTypes

	Note: The design may seem a little weird, but it exists exists to
		ensure backward compatibility. The correct way to use this function is to
		pass a dict to doctype as described below

	NEW FUNCTIONALITY
	=================
	Parameters:
	doctype (dict):
		key (string): DocType name
		value (list): of strings of doc names which need to be concatenated and printed
	name (string):
		name of the pdf which is generated
	format:
		Print Format to be used

	Returns:
	PDF: A PDF generated by the concatenation of the mentioned input docs

	OLD FUNCTIONALITY - soon to be deprecated
	=========================================
	Parameters:
	doctype (string):
		name of the DocType to which the docs belong which need to be printed
	name (string or list):
		If string the name of the doc which needs to be printed
		If list the list of strings of doc names which needs to be printed
	format:
		Print Format to be used

	Returns:
	PDF: A PDF generated by the concatenation of the mentioned input docs
	"""

	import json
	output = PdfFileWriter()

	if not isinstance(doctype, dict):
		result = json.loads(name)

		# Concatenating pdf files
		for i, ss in enumerate(result):
			output = frappe.get_print(doctype, ss, format, as_pdf = True, output = output, no_letterhead=no_letterhead)
		frappe.local.response.filename = "{doctype}.pdf".format(doctype=doctype.replace(" ", "-").replace("/", "-"))
	else:
		for doctype_name in doctype:
			for doc_name in doctype[doctype_name]:
				try:
					output = frappe.get_print(doctype_name, doc_name, format, as_pdf = True, output = output, no_letterhead=no_letterhead)
				except Exception:
					frappe.log_error("Permission Error on doc {} of doctype {}".format(doc_name, doctype_name))
		frappe.local.response.filename = "{}.pdf".format(name)

	frappe.local.response.filecontent = read_multi_pdf(output)
	frappe.local.response.type = "download"

def read_multi_pdf(output):
	# Get the content of the merged pdf files
	fname = os.path.join("/tmp", "frappe-pdf-{0}.pdf".format(frappe.generate_hash()))
	output.write(open(fname,"wb"))

	with open(fname, "rb") as fileobj:
		filedata = fileobj.read()

	return filedata

@frappe.whitelist()
def download_pdf(doctype, name, format=None, doc=None, no_letterhead=0):
	html = frappe.get_print(doctype, name, format, doc=doc, no_letterhead=no_letterhead)
	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "pdf"

@frappe.whitelist()
def report_to_pdf(html, orientation="Landscape"):
	make_access_log(file_type='PDF', method='PDF', page=html)
	frappe.local.response.filename = "report.pdf"
	frappe.local.response.filecontent = get_pdf(html, {"orientation": orientation})
	frappe.local.response.type = "pdf"

@frappe.whitelist()
def print_by_server(doctype, name, printer_setting, print_format=None, doc=None, no_letterhead=0):
	print_settings = frappe.get_doc("Network Printer Settings", printer_setting)
	try:
		import cups
	except ImportError:
		frappe.throw(_("You need to install pycups to use this feature!"))

	try:
		cups.setServer(print_settings.server_ip)
		cups.setPort(print_settings.port)
		conn = cups.Connection()
		output = PdfFileWriter()
		output = frappe.get_print(doctype, name, print_format, doc=doc, no_letterhead=no_letterhead, as_pdf = True, output = output)
		file = os.path.join("/", "tmp", "frappe-pdf-{0}.pdf".format(frappe.generate_hash()))
		output.write(open(file,"wb"))
		conn.printFile(print_settings.printer_name,file , name, {})
	except IOError as e:
		if ("ContentNotFoundError" in e.message
			or "ContentOperationNotPermittedError" in e.message
			or "UnknownContentError" in e.message
			or "RemoteHostClosedError" in e.message):
			frappe.throw(_("PDF generation failed"))
	except cups.IPPError:
		frappe.throw(_("Printing failed"))
	finally:
		return
