"""Check generated synthetic PDF/Word documents (QA-only pdfplumber required)."""
from pathlib import Path
import argparse
import json
import re
import pdfplumber
from docx import Document
from docx.oxml.ns import qn


def verify(root):
    results=[]
    for case in sorted(Path(root).glob('[0-9]*')):
        markdown=(case/'fixture.md').read_text(encoding='utf-8')
        expected=markdown.count('<img ')
        with pdfplumber.open(case/'fixture.pdf') as pdf:
            text='';images=0
            for page in pdf.pages:
                assert abs(page.width-595.28)<.1 and abs(page.height-841.89)<.1
                text+=page.extract_text() or ''
                for im in page.images:
                    assert 55<=im['x0']<im['x1']<=540, case.name
                    assert 53<=im['top']<im['bottom']<=789, case.name
                    assert 0<im['height']<=360.1, case.name
                    images+=1
            assert images==expected,case.name
            assert '2026-01-02' in text,case.name
            if case.name.startswith('19'):assert 'Final entry' in text
            if case.name.startswith('20'):assert 'FINAL CONTENT' in text and len(pdf.pages)>1
            count=len(pdf.pages)
        doc=Document(case/'fixture.docx')
        assert len(doc.inline_shapes)==expected,case.name
        section=doc.sections[0]
        usable=(section.page_width-section.left_margin-section.right_margin)/12700
        for shape in doc.inline_shapes:
            assert 0<shape.width.pt<=usable and 0<shape.height.pt<=360.1,case.name
        for table in doc.tables:
            borders=table._tbl.tblPr.find(qn('w:tblBorders'))
            assert borders is not None and len(borders)==6,case.name
            assert all(edge.get(qn('w:val'))=='nil' for edge in borders),case.name
            assert sum(column.width.pt for column in table.columns)<=usable+.1,case.name
        tex=(case/'fixture.tex').read_text(encoding='utf-8')
        refs=re.findall(r'\\includegraphics\[[^\]]+\]\{([^}]+)\}',tex)
        assert len(refs)==expected,case.name
        assert all(ref.startswith('assets/') and (case/ref).is_file() for ref in refs),case.name
        results.append({'case':case.name,'pages':count,'images':images,'pdfBounds':'passed','docxStructure':'passed','texAssets':'passed'})
    assert len(results)==20,'Expected all 20 cases'
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    args=parser.parse_args()
    results=verify(args.root)
    (args.root/'renderer-checks.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: {len(results)} synthetic cases; PDF geometry/text, DOCX structure, TeX assets')
