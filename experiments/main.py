from jobsdb_url_builder import JobsDBURLBuilder
from docling.document_converter import DocumentConverter

builder = JobsDBURLBuilder("Software Engineer")
print(builder.build())
source = builder.build()  # file path or URL
converter = DocumentConverter()
doc = converter.convert(source).document

print(doc.export_to_markdown())  # output: "### Docling Technical Report[...]"
