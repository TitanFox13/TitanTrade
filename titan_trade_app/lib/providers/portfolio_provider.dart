import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import '../models/portfolio.dart';
import 'config_provider.dart';

final portfolioProvider = StreamProvider<Portfolio>((ref) async* {
  final pathAsync = ref.watch(dataPathProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final root = pathAsync.valueOrNull;
  if (root == null) return;

  final file = File(p.join(root, 'state', 'portfolio.json'));
  while (true) {
    if (file.existsSync()) {
      try {
        final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        yield Portfolio.fromJson(json);
      } on FormatException {
        // File might be mid-write; skip this cycle
      }
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
