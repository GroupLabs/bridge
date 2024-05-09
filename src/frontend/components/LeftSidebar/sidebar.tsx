import React from 'react';

const Sidebar = ({ files }) => {
  return (
    <aside className="w-1/5 h-[calc(100%-64px)] bg-gray-100 p-4 shadow-md fixed top-16">
      <h2 className="text-xl font-bold mb-4">Uploaded Files</h2>
      <ul className="space-y-2">
        {files.length > 0 ? (
          files.map((file, index) => (
            <li key={index} className="text-sm text-gray-700">
              {file.name}
            </li>
          ))
        ) : (
          <li className="text-sm text-gray-500">No files uploaded</li>
        )}
      </ul>
    </aside>
  );
};

export default Sidebar;
