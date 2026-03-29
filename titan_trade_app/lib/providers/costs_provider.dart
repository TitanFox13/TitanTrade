import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import '../models/cost_record.dart';
import 'config_provider.dart';

final costsProvider = StreamProvider<List<CostRecord>>((ref) async* {
  final pathAsync = ref.watch(dataPathProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final rootPath = pathAsync.valueOrNull;
  if (rootPath == null) {
    yield [];
    return;
  }

  final filePath = p.join(rootPath, 'state', 'costs.json');

  while (true) {
    try {
      final file = File(filePath);
      if (file.existsSync()) {
        final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        final list = (json['costs'] as List<dynamic>?) ?? [];
        final records = list
            .map((e) => CostRecord.fromJson(e as Map<String, dynamic>))
            .toList()
          ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
        yield records;
      } else {
        yield [];
      }
    } catch (_) {
      yield [];
    }
    await Future.delayed(Duration(seconds: refreshSeconds));
  }
});
