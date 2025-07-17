import React, { useEffect, useState } from 'react';

interface Candidate {
  crop_png?: string;
  preview_png?: string;
  dxf_file?: string;
  bbox: [number, number, number, number];
  size: [number, number];
}

interface TestRecord {
  name: string;
  source_image: string;
  corrected_image: string;
  phase1: any;
  phase2: {
    candidates: Candidate[];
  };
}

interface ProofingData {
  tests: TestRecord[];
}

const ProofingReport: React.FC = () => {
  const [data, setData] = useState<ProofingData | null>(null);

  useEffect(() => {
    fetch('/results/proofing_report.json')
      .then((res) => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  if (!data) return <div className="p-4">Loading...</div>;

  return (
    <div className="min-h-screen bg-gray-100 p-4 space-y-8">
      {data.tests.map((test) => (
        <section key={test.name} className="bg-white rounded-lg shadow p-4 space-y-4">
          <h2 className="text-xl font-semibold">{test.name}</h2>

          <div className="flex space-x-4">
            <div>
              <p className="text-sm text-gray-600">Source image:</p>
              <img src={test.source_image} alt="Source" className="max-w-xs border rounded" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Corrected image:</p>
              <img src={test.corrected_image} alt="Corrected" className="max-w-xs border rounded" />
            </div>
          </div>

          <h3 className="text-lg font-medium">Candidates</h3>
          <div className="space-y-4">
            {test.phase2.candidates.map((cand, i) => (
              <div key={i} className="border p-3 rounded bg-gray-50">
                <div className="flex space-x-4">
                  {cand.crop_png && <img src={cand.crop_png} alt="Crop" className="max-w-xs border rounded" />}
                  {cand.preview_png && <img src={cand.preview_png} alt="Preview" className="max-w-xs border rounded" />}
                </div>
                <p className="mt-2">
                  {cand.dxf_file && (
                    <a href={cand.dxf_file} className="text-blue-600 underline" download>
                      Download DXF
                    </a>
                  )}
                </p>
                <pre className="mt-2 bg-white p-2 rounded text-sm overflow-x-auto">
                  {JSON.stringify(cand, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
};

export default ProofingReport;