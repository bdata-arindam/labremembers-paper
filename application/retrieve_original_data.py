"""Retrieve the authors' original measured workbook without modifying it.

The article is CC BY-NC 4.0. The separate data repository has no explicit license
notice in the inspected metadata. This script does not relabel the workbook MIT.
"""
from pathlib import Path
from urllib.request import urlopen
import hashlib
import json
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
COMMIT='226c2f0df03a645166d793c4a4b76a4744af015e'
URL=f'https://raw.githubusercontent.com/the-matter-lab/quaterny_opvs/{COMMIT}/experimental_data.xlsx'
EXPECTED_SHA='69ae8917cd63fe9391278df86722c0ebc2921af92dd1b27d9b957cb030a074ad'
TARGET=HERE/'quaterny_opvs_experimental_data.xlsx'
with urlopen(URL,timeout=45) as response:
    body=response.read()
sha=hashlib.sha256(body).hexdigest()
if sha!=EXPECTED_SHA:raise RuntimeError(f'Unexpected source hash: {sha}')
if not body.startswith(b'PK'):raise RuntimeError('Expected XLSX ZIP signature')
TARGET.write_bytes(body)
manifest={'filename':TARGET.name,'source_url':URL,'repository':'https://github.com/the-matter-lab/quaterny_opvs',
          'repository_commit':COMMIT,'original_repository_url_in_article':'http://github.com/aspuru-guzik-group/quaterny_opvs',
          'retrieved_utc':datetime.now(timezone.utc).isoformat(),'bytes':len(body),'sha256':sha,
          'source_doi':'10.1002/adma.201907801','article_license':'CC BY-NC 4.0',
          'data_repository_license':'No explicit repository license found; API license field null. Article license not assumed automatically to cover separate workbook.',
          'redistribution_note':'Research download retained with provenance. Do not relabel this workbook MIT. License clarification remains relevant before redistributing original workbook in a public research package.'}
(HERE/'original_download_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
