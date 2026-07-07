export default function EmptyChatNotice() {
  return (
    <div className="flex flex-col items-center justify-center h-full p-4">
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 max-w-md w-full shadow-sm flex items-start gap-3">
        <div className="bg-amber-100 p-2 rounded-lg text-amber-600">
          <i className="fa-solid fa-triangle-exclamation"></i>
        </div>
        <div>
          <h3 className="font-bold text-amber-800 text-sm">Empty Chat</h3>
          <p className="text-amber-700 text-xs mt-1">Lets write first message!</p>
        </div>
      </div>
    </div>
  );
}
