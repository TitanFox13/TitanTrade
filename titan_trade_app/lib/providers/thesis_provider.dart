import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import '../models/thesis.dart';
import 'config_provider.dart';

final thesisProvider = StreamProvider<WeeklyThesisBundle?>((ref) async* {
  final pathAsync = ref.watch(dataPathProvider);
  final refreshSeconds = ref.watch(refreshIntervalProvider);
  final root = pathAsync.valueOrNull;
  if (root == null) return;

  final file = File(p.join(root, 'state', 'weekly_thesis.json'));
  while (true) {
    if (file.existsSync()) {
      try {
        final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        yield WeeklyThesisBundle.fromJson(json);
      } on FormatException {
        // skip
      }
    } else {
      yield null;
    }
    await Future<void>.delayed(Duration(seconds: refreshSeconds));
  }
});
