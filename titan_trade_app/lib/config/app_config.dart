import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';

const _key = 'titan_trade_data_path';
const _refreshKey = 'titan_trade_refresh_seconds';
const defaultRefreshSeconds = 30;

Future<String?> loadDataPath() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString(_key);
}

Future<void> saveDataPath(String path) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(_key, path);
}

Future<int> loadRefreshInterval() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getInt(_refreshKey) ?? defaultRefreshSeconds;
}

Future<void> saveRefreshInterval(int seconds) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setInt(_refreshKey, seconds);
}

bool validateDataPath(String path) {
  return File(p.join(path, 'state', 'portfolio.json')).existsSync();
}

String statePath(String root) => p.join(root, 'state');
String logsPath(String root) => p.join(root, 'logs');
