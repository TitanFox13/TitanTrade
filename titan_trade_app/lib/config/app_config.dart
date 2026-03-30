import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const _urlKey = 'titan_trade_base_url';
const _refreshKey = 'titan_trade_refresh_seconds';
const defaultRefreshSeconds = 30;

Future<String?> loadBaseUrl() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString(_urlKey);
}

Future<void> saveBaseUrl(String url) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(_urlKey, url);
}

Future<int> loadRefreshInterval() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getInt(_refreshKey) ?? defaultRefreshSeconds;
}

Future<void> saveRefreshInterval(int seconds) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setInt(_refreshKey, seconds);
}

/// Validates a server URL by hitting /api/health. Returns true if reachable.
Future<bool> validateBaseUrl(String url) async {
  try {
    final uri = Uri.parse('$url/api/health');
    final response = await http.get(uri).timeout(const Duration(seconds: 5));
    return response.statusCode == 200;
  } catch (_) {
    return false;
  }
}
