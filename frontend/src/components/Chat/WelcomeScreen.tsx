export default function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-24 h-24 bg-white rounded-3xl flex items-center justify-center mb-6 shadow-xl shadow-gray-200 border border-gray-100">
        <i className="fa-solid fa-robot text-4xl text-blue-600"></i>
      </div>
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Smart Document Search System</h2>
      <p className="text-gray-500 max-w-md">
        Upload your documents and ask me to create presentations, Word files, PDFs, checklists, or comparison tables —
        or search the web.
      </p>
    </div>
  );
}
