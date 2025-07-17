import React, { useState } from 'react';
import { 
  Camera, 
  Settings, 
  Download, 
  FileText, 
  Image, 
  CheckCircle, 
  AlertCircle,
  Eye,
  Layers,
  Grid,
  Zap,
  Clock,
  MapPin,
  Database
} from 'lucide-react';

interface CandidateItem {
  id: string;
  sourceImage: string;
  confidence: number;
  status: 'processed' | 'processing' | 'failed';
  metadata: {
    dimensions: string;
    fileSize: string;
    format: string;
    timestamp: string;
    location?: string;
    quality: number;
  };
  downloads: {
    dxf: string;
    dxc: string;
  };
}

const ProofingReport: React.FC = () => {
  const [selectedView, setSelectedView] = useState<'original' | 'corrected'>('original');
  
  const candidateItems: CandidateItem[] = [
    {
      id: '001',
      sourceImage: 'https://images.pexels.com/photos/1172849/pexels-photo-1172849.jpeg?auto=compress&cs=tinysrgb&w=400',
      confidence: 0.94,
      status: 'processed',
      metadata: {
        dimensions: '4032x3024',
        fileSize: '2.4 MB',
        format: 'JPEG',
        timestamp: '2024-01-15T14:30:22Z',
        location: 'Wall Section A',
        quality: 95
      },
      downloads: {
        dxf: '/downloads/wall-section-a.dxf',
        dxc: '/downloads/wall-section-a.dxc'
      }
    },
    {
      id: '002',
      sourceImage: 'https://images.pexels.com/photos/1080696/pexels-photo-1080696.jpeg?auto=compress&cs=tinysrgb&w=400',
      confidence: 0.87,
      status: 'processed',
      metadata: {
        dimensions: '3840x2160',
        fileSize: '3.1 MB',
        format: 'JPEG',
        timestamp: '2024-01-15T14:32:45Z',
        location: 'Wall Section B',
        quality: 92
      },
      downloads: {
        dxf: '/downloads/wall-section-b.dxf',
        dxc: '/downloads/wall-section-b.dxc'
      }
    },
    {
      id: '003',
      sourceImage: 'https://images.pexels.com/photos/1181406/pexels-photo-1181406.jpeg?auto=compress&cs=tinysrgb&w=400',
      confidence: 0.76,
      status: 'processing',
      metadata: {
        dimensions: '4608x3456',
        fileSize: '2.8 MB',
        format: 'JPEG',
        timestamp: '2024-01-15T14:35:12Z',
        location: 'Wall Section C',
        quality: 88
      },
      downloads: {
        dxf: '/downloads/wall-section-c.dxf',
        dxc: '/downloads/wall-section-c.dxc'
      }
    }
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'processed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'processing':
        return <Zap className="w-4 h-4 text-amber-500 animate-pulse" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'processed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-amber-100 text-amber-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-600';
    if (confidence >= 0.7) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-gray-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-3">
              <div className="flex items-center justify-center w-10 h-10 bg-blue-600 rounded-lg">
                <Camera className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-gray-900">Surface Analysis Report</h1>
                <p className="text-sm text-gray-500">Perspective Correction & Feature Detection</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <div className="text-sm text-gray-500">
                Session: <span className="font-medium">20240115-143022</span>
              </div>
              <button className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors">
                <Settings className="w-4 h-4 mr-2" />
                Settings
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Image Comparison Section */}
        <div className="bg-white rounded-xl shadow-lg border border-gray-200 mb-8">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Image className="w-5 h-5 text-blue-600" />
                <h2 className="text-lg font-semibold text-gray-900">Image Processing Results</h2>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setSelectedView('original')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    selectedView === 'original'
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  <Eye className="w-4 h-4 mr-2 inline" />
                  Original
                </button>
                <button
                  onClick={() => setSelectedView('corrected')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    selectedView === 'corrected'
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  <Layers className="w-4 h-4 mr-2 inline" />
                  Corrected
                </button>
              </div>
            </div>
          </div>
          
          <div className="p-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
                  <span className="text-sm font-medium text-gray-700">Raw Capture</span>
                </div>
                <div className="relative group">
                  <img
                    src="https://images.pexels.com/photos/1172849/pexels-photo-1172849.jpeg?auto=compress&cs=tinysrgb&w=800"
                    alt="Raw surface capture"
                    className="w-full h-64 object-cover rounded-lg border border-gray-300 shadow-sm"
                  />
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-10 transition-all rounded-lg"></div>
                </div>
                <div className="flex items-center space-x-4 text-sm text-gray-600">
                  <div className="flex items-center space-x-1">
                    <Grid className="w-4 h-4" />
                    <span>4032×3024</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Database className="w-4 h-4" />
                    <span>2.4 MB</span>
                  </div>
                </div>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span className="text-sm font-medium text-gray-700">Perspective Corrected</span>
                </div>
                <div className="relative group">
                  <img
                    src="https://images.pexels.com/photos/1080696/pexels-photo-1080696.jpeg?auto=compress&cs=tinysrgb&w=800"
                    alt="Corrected surface"
                    className="w-full h-64 object-cover rounded-lg border border-gray-300 shadow-sm"
                  />
                  <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-10 transition-all rounded-lg"></div>
                </div>
                <div className="flex items-center space-x-4 text-sm text-gray-600">
                  <div className="flex items-center space-x-1">
                    <Grid className="w-4 h-4" />
                    <span>3840×2160</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span>Aligned</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Candidate Items Table */}
        <div className="bg-white rounded-xl shadow-lg border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <FileText className="w-5 h-5 text-blue-600" />
                <h2 className="text-lg font-semibold text-gray-900">Detected Features</h2>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {candidateItems.length} items
                </span>
              </div>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Source Image
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Confidence
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Metadata
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Downloads
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {candidateItems.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center space-x-3">
                        <img
                          src={item.sourceImage}
                          alt={`Source ${item.id}`}
                          className="w-12 h-12 rounded-lg object-cover border border-gray-300"
                        />
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            Item {item.id}
                          </div>
                          {item.metadata.location && (
                            <div className="flex items-center space-x-1 text-xs text-gray-500">
                              <MapPin className="w-3 h-3" />
                              <span>{item.metadata.location}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(item.status)}
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(item.status)}`}>
                          {item.status}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center space-x-2">
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full transition-all ${
                              item.confidence >= 0.9 ? 'bg-green-500' :
                              item.confidence >= 0.7 ? 'bg-amber-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${item.confidence * 100}%` }}
                          ></div>
                        </div>
                        <span className={`text-sm font-medium ${getConfidenceColor(item.confidence)}`}>
                          {(item.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2 text-sm text-gray-600">
                          <Grid className="w-3 h-3" />
                          <span>{item.metadata.dimensions}</span>
                        </div>
                        <div className="flex items-center space-x-2 text-sm text-gray-600">
                          <Database className="w-3 h-3" />
                          <span>{item.metadata.fileSize}</span>
                        </div>
                        <div className="flex items-center space-x-2 text-sm text-gray-600">
                          <Clock className="w-3 h-3" />
                          <span>{new Date(item.metadata.timestamp).toLocaleString()}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex space-x-2">
                        <button
                          disabled={item.status !== 'processed'}
                          className={`inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md transition-colors ${
                            item.status === 'processed'
                              ? 'text-blue-700 bg-blue-100 hover:bg-blue-200'
                              : 'text-gray-400 bg-gray-100 cursor-not-allowed'
                          }`}
                        >
                          <Download className="w-3 h-3 mr-1" />
                          DXF
                        </button>
                        <button
                          disabled={item.status !== 'processed'}
                          className={`inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md transition-colors ${
                            item.status === 'processed'
                              ? 'text-purple-700 bg-purple-100 hover:bg-purple-200'
                              : 'text-gray-400 bg-gray-100 cursor-not-allowed'
                          }`}
                        >
                          <Download className="w-3 h-3 mr-1" />
                          DXC
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProofingReport;