import 'package:flutter/material.dart';

const _gainGreen = Color(0xFF4CAF50);
const _lossRed = Color(0xFFEF5350);

final titanTheme = ThemeData(
  brightness: Brightness.dark,
  colorSchemeSeed: Colors.teal,
  useMaterial3: true,
  fontFamily: 'Segoe UI',
  cardTheme: const CardThemeData(
    elevation: 0,
    margin: EdgeInsets.symmetric(vertical: 4, horizontal: 0),
  ),
);

Color pnlColor(double value) => value >= 0 ? _gainGreen : _lossRed;

const monoStyle = TextStyle(fontFamily: 'Consolas', fontFamilyFallback: ['monospace']);
