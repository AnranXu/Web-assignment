#include <iostream>
#include <fstream>
#include <string>
using namespace std;
int main()
{
	string s;
	ifstream infile("URG_X_20130903_195003.lms", ios::binary);
	ofstream outfile("a.txt",ios::binary);
	while (getline(infile, s))
	{ 
		//cout << s << endl;
		outfile << s << endl;
	}
}