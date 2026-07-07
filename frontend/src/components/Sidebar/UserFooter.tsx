import { USER_ID } from "../../lib/api";

export default function UserFooter() {
  return (
    <div className="p-4 border-t border-gray-100 bg-gray-50">
      <div className="flex items-center gap-3 w-full p-2">
        <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-blue-500 to-cyan-500 flex items-center justify-center text-white font-bold shadow-sm">
          {USER_ID.slice(0, 2).toUpperCase()}
        </div>
        <div className="text-left flex-1">
          <p className="text-sm font-semibold text-gray-700">{USER_ID}</p>
          <p className="text-xs text-green-600 font-medium">● Online</p>
        </div>
      </div>
    </div>
  );
}
