'use client';

import React, { useState } from 'react';
import { CitizenLanguage, CitizenSchemeCard } from '@/types/citizen';
import SchemeCard from './SchemeCard';

interface ResultsListProps {
  eligibleSchemes: CitizenSchemeCard[];
  moreInfoSchemes: CitizenSchemeCard[];
  language: CitizenLanguage;
  onSelectScheme: (schemeId: string) => void;
  onContinueQuestions?: () => void;
  hasNextQuestion?: boolean;
  onResetNeed?: () => void;
}

export const ResultsList: React.FC<ResultsListProps> = ({
  eligibleSchemes,
  moreInfoSchemes,
  language,
  onSelectScheme,
  onContinueQuestions,
  hasNextQuestion = false,
  onResetNeed,
}) => {
  const isHi = language === 'hi';
  const [showAllEligible, setShowAllEligible] = useState(false);
  const [showAllMoreInfo, setShowAllMoreInfo] = useState(false);

  const INITIAL_LIMIT = 4;

  const displayedEligible = showAllEligible
    ? eligibleSchemes
    : eligibleSchemes.slice(0, INITIAL_LIMIT);

  const displayedMoreInfo = showAllMoreInfo
    ? moreInfoSchemes
    : moreInfoSchemes.slice(0, INITIAL_LIMIT);

  const totalCount = eligibleSchemes.length + moreInfoSchemes.length;

  if (totalCount === 0) {
    return (
      <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm text-center max-w-xl mx-auto my-6">
        <div className="w-16 h-16 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 className="text-xl font-bold text-slate-800 mb-2">
          {isHi ? 'कोई उपयुक्त योजना नहीं मिली' : 'No Suitable Schemes Found'}
        </h3>
        <p className="text-slate-600 leading-relaxed mb-6">
          {isHi
            ? 'अभी दी गई जानकारी के आधार पर कोई उपयुक्त सत्यापित योजना नहीं मिली। आप अपनी आवश्यकता बदलकर फिर से खोज सकते हैं।'
            : 'Based on the information provided, no verified matching schemes were found. You can try searching with a different need or updating your details.'}
        </p>
        {onResetNeed && (
          <button
            onClick={onResetNeed}
            className="px-6 py-3 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-700 transition shadow-sm"
          >
            {isHi ? 'नई आवश्यकता से खोजें' : 'Search with New Need'}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-8 w-full max-w-3xl mx-auto">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">
            {isHi ? 'खोज परिणाम' : 'Discovery Results'}
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {isHi
              ? `कुल ${totalCount} योजनाएँ आपके विवरण से संबंधित हैं`
              : `Total ${totalCount} schemes relevant to your details`}
          </p>
        </div>

        {hasNextQuestion && onContinueQuestions && (
          <button
            onClick={onContinueQuestions}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl hover:bg-emerald-100 transition shadow-xs"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {isHi ? 'और सटीक परिणाम चाहिए' : 'Refine with More Questions'}
          </button>
        )}
      </div>

      {/* SECTION 1: CONFIRMED ELIGIBLE */}
      {eligibleSchemes.length > 0 && (
        <section aria-labelledby="eligible-heading" className="space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <h3 id="eligible-heading" className="text-lg font-bold text-emerald-900">
              {isHi ? 'दी गई जानकारी के आधार पर पात्र' : 'Schemes you appear eligible for'}
              <span className="ml-2 text-sm font-semibold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                {eligibleSchemes.length}
              </span>
            </h3>
          </div>

          <p className="text-xs text-slate-500 -mt-1">
            {isHi
              ? 'यह परिणाम आपके द्वारा दर्ज की गई जानकारी और सरकार द्वारा सत्यापित नियमों के अनुसार है।'
              : 'These results are matched deterministically based on your provided information and verified rules.'}
          </p>

          <div className="grid gap-4">
            {displayedEligible.map((scheme) => (
              <SchemeCard
                key={scheme.scheme_id}
                scheme={scheme}
                language={language}
                onSelect={() => onSelectScheme(scheme.scheme_id)}
              />
            ))}
          </div>

          {eligibleSchemes.length > INITIAL_LIMIT && (
            <div className="text-center pt-2">
              <button
                onClick={() => setShowAllEligible(!showAllEligible)}
                className="text-sm font-semibold text-emerald-700 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 px-5 py-2.5 rounded-xl transition inline-flex items-center gap-1.5"
              >
                {showAllEligible
                  ? isHi ? 'कम योजनाएँ देखें' : 'Show Fewer Schemes'
                  : isHi ? `और ${eligibleSchemes.length - INITIAL_LIMIT} योजनाएँ देखें` : `Show ${eligibleSchemes.length - INITIAL_LIMIT} More Schemes`}
                <svg className={`w-4 h-4 transition-transform ${showAllEligible ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
          )}
        </section>
      )}

      {/* SECTION 2: MORE INFORMATION NEEDED */}
      {moreInfoSchemes.length > 0 && (
        <section aria-labelledby="more-info-heading" className="space-y-4 pt-4 border-t border-slate-200">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
            <h3 id="more-info-heading" className="text-lg font-bold text-amber-950">
              {isHi ? 'इन योजनाओं के लिए कुछ और जानकारी चाहिए' : 'Additional Information Needed For These Schemes'}
              <span className="ml-2 text-sm font-semibold text-amber-800 bg-amber-100 px-2 py-0.5 rounded-full">
                {moreInfoSchemes.length}
              </span>
            </h3>
          </div>

          <p className="text-xs text-slate-500 -mt-1">
            {isHi
              ? 'ये योजनाएँ आपकी आवश्यकता से मेल खाती हैं, लेकिन पात्रता निश्चित करने के लिए अतिरिक्त विवरण आवश्यक है।'
              : 'These schemes match your stated need, but require additional criteria to confirm eligibility.'}
          </p>

          <div className="grid gap-4">
            {displayedMoreInfo.map((scheme) => (
              <SchemeCard
                key={scheme.scheme_id}
                scheme={scheme}
                language={language}
                onSelect={() => onSelectScheme(scheme.scheme_id)}
              />
            ))}
          </div>

          {moreInfoSchemes.length > INITIAL_LIMIT && (
            <div className="text-center pt-2">
              <button
                onClick={() => setShowAllMoreInfo(!showAllMoreInfo)}
                className="text-sm font-semibold text-amber-800 hover:text-amber-900 bg-amber-50 hover:bg-amber-100 px-5 py-2.5 rounded-xl transition inline-flex items-center gap-1.5"
              >
                {showAllMoreInfo
                  ? isHi ? 'कम योजनाएँ देखें' : 'Show Fewer Schemes'
                  : isHi ? `और ${moreInfoSchemes.length - INITIAL_LIMIT} योजनाएँ देखें` : `Show ${moreInfoSchemes.length - INITIAL_LIMIT} More Schemes`}
                <svg className={`w-4 h-4 transition-transform ${showAllMoreInfo ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default ResultsList;
